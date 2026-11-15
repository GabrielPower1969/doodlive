#!/usr/bin/env python3
"""Original score and sound effects for "Jonah and the Big Fish" (story pack `jonah`; docs/jonah/CONTRACT.md section 7,
docs/jonah/MUSIC.md).

Built on the shared engine tools/story/music_kit.py (`import music_kit as me`): Score / Part / mel / groove / Ctx, the
FluidSynth renderer, the convolution hall, loudness and file helpers, the synthesis primitives. This script holds only
Jonah's cues, effects, paths and tables, plus the loop-section / build machinery that the kit does not have yet (copied
from music_daniel.py, see docs/jonah/MUSIC.md "Reuse").

Two original themes carry the score:
  * the CALL theme (God's voice): a calm rising four-note figure C-F-G-Bb in F major on a warm horn and cello
    (CALL below). Heard in `call` (twice: file reused at S08), `prayer` (horn, answered by the solo cello), `repent`
    (at the forgiving chime) and `mercy` (in full).
  * the JONAH theme: a grumpy, plodding bassoon tune in D minor (JONAH below). It sneaks in `runaway`, interrupts the
    call in `call` ("No way!"), confesses in `storm` (S04), marches in `sulk` at its grumpiest, droops in `plant`
    and turns gentle (F major, same degrees) in `mercy`, where it is played together with the call theme.
Every melody is original; nothing is taken from any film.

Every name and time comes from assets/jonah/timeline.json, read on every run (cue spans from the music events,
in-cue hits looked up by sfx / lines events). After the voices re-time the play, rerun this script. Every cue
continues after its cadence into a quiet loop section on its final chord: cues.json has sample-exact loop points
(loopStart / loopEnd); each file is >= 1.3 x its span + 0.6 s. `call` plays twice (S01 and S08): one file, composed
for the longer S01.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/jonah/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated over the composed span, true peak <= -1 dBTP
  assets/jonah/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/jonah/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/jonah/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain, loop hints
  assets/jonah/audio/preview_mix.mp3        full-length mix at timeline times (zh voice clips, music ducked 7 dB)
  docs/jonah/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_jonah.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR] [--spec DIR]   (scratch default /tmp/jonah_music; --spec writes spectrogram PNGs of every output)
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
                       HARP, KOTO, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                       CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, SHANAI, TIMPANI, TRUMPET, TROMBONE, TUBA, HORN, DRUMS,
                       BDRUM, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA, HI_WOOD, LO_WOOD,
                       SHAKER, TRIANGLE, SNARE)

ROOT = me.ROOT
JO = f"{ROOT}/assets/jonah"
TIMELINE = f"{JO}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{JO}/audio/music", f"{JO}/audio/sfx", f"{JO}/audio/voice/zh"
PREVIEW = f"{JO}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/jonah/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -4.5             # loop section loudness relative to the cue's composed span (was -3: quieter bed under voices)
SPAN_LUFS = -20.9              # composed span loudness (contract -20 +-1: 0.9 under it, check.py allows 1.0)
NO_SWELL = {'call'}            # `call` plays at S01 and S08 from one file: its chime-time swell would land under S08's speech
# extra dips (file seconds, zh re-timed play, dB) where a cue sits under a line it cannot get out of the way of
DIPS = {"call": [(6.5, 15.2, -6.5)], "storm": [(0.8, 5.6, -4.0), (27.8, 33.8, -2.5), (34.25, 40.0, -8.0)], "deep": [(15.3, 20.3, -3.0)],
        "prayer": [(5.7, 13.0, -4.0), (13.9, 22.3, -3.0)], "mercy": [(0.6, 10.4, -4.0)]}
HIT_SFX = {'thunder', 'splash_big', 'gulp', 'burp', 'spit_pop', 'grow_whoosh', 'munch'}
HIT_FX = {'prayer_glow', 'heart_glow'}
TMP_PREFIX = "music_jonah_"

# extra GM programs (0-based)
VIOLA, ENGLISH_HORN, PAN_FLUTE, MUSIC_BOX = 41, 69, 75, 10

CH = dict(me.CH)
CH.update({"Dm": ["D3", "A3", "D4", "F4"], "D": ["D3", "A3", "D4", "F#4"], "Dm7": ["D3", "A3", "C4", "F4"],
           "F": ["F2", "C3", "F3", "A3"], "Fmaj7": ["F2", "C3", "E3", "A3"], "Fsus": ["F2", "C3", "F3", "Bb3"],
           "Bb": ["Bb2", "F3", "Bb3", "D4"], "Gm": ["G2", "D3", "G3", "Bb3"], "C": ["C3", "G3", "C4", "E4"],
           "C7": ["C3", "G3", "Bb3", "E4"], "Am": ["A2", "E3", "A3", "C4"], "A": ["A2", "E3", "A3", "C#4"],
           "Eb": ["Eb3", "Bb3", "Eb4", "G4"], "Edim": ["E3", "Bb3", "E4", "G4"], "Cm": ["C3", "G3", "C4", "Eb4"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def nm(m): return f"{NAMES[m % 12]}{m // 12 - 1}"


# =============================================================================================== the two themes
# The CALL theme, F major (4/4). The four rising notes C-F-G-Bb are the figure; bar 2 lands on Bb and eases to A.
CALL = {
    1: [("C4", 2), ("F4", 1), ("G4", 1)],
    2: [("Bb4", 3), ("A4", 1)],
    3: [("G4", 1.5), ("A4", .5), ("F4", 1), ("G4", 1)],
    4: [("F4", 4)],
}
CALL_HARM = {1: ["F"], 2: ["Bb", "C"], 3: ["Gm", "C"], 4: ["F"]}
# The JONAH theme, D minor: heavy repeated notes, a stubborn step up, a sigh down. JONAH_MAJOR re-pitches the same
# degrees in F major (D->F, E->G, F->A, G->Bb, A->C, Bb->D) for the gentle form in `mercy`.
JONAH = {
    1: [("D3", 1), ("D3", .5), ("D3", .5), ("F3", 1), ("D3", 1)],
    2: [("E3", 1), ("E3", .5), ("E3", .5), ("G3", 1), ("E3", 1)],
    3: [("F3", 1), ("G3", 1), ("A3", 1.5), ("Bb3", .5)],
    4: [("A3", 1), ("G3", 1), ("F3", 1), ("D3", 1)],
}
JONAH_HARM = {1: ["Dm"], 2: ["C"], 3: ["F", "Dm"], 4: ["Dm"]}
JONAH_HARM_MAJOR = {1: ["F"], 2: ["Bb"], 3: ["F", "Bb"], 4: ["C", "F"]}
_JM = {2: 3, 4: 3, 5: 4, 7: 3, 9: 3, 10: 4, 0: 4}


def call(bars, scale=1.0):
    out = []
    for k in bars: out += [(p, d * scale) for p, d in CALL[k]]
    return out


def jonah(bars, major=False, stacc=False, scale=1.0):
    """Jonah theme bars; major=True gives the F major form; stacc=True the tiptoe (staccato) form."""
    out = []
    for k in bars:
        for p, d in JONAH[k]:
            if major: p = nm(note(p) + _JM[note(p) % 12])
            out.append((p + ("." if stacc else ""), d * scale))
    return out


def harm_at(part_fn, b0, harm, beats):
    for i, h in enumerate(harm): part_fn(b0 + i * beats / len(harm), h, beats / len(harm))


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


F_SCALE = ["F", "G", "A", "Bb", "C", "D", "E"]
def scale_run(lo, hi, names=F_SCALE):
    pcs = {note(n + "4") % 12 for n in names}
    return [m for m in range(note(lo), note(hi) + 1) if m % 12 in pcs]


# Sustain fix (Ruth, measured 2026-11-14): the macOS DLS bank as FluidSynth loads it decays every instrument; winds,
# bowed strings, brass and voices get an NRPN offset on SoundFont gen 37 (volEnvSustain -1440 cB) so long notes hold.
SUSTAIN = {STRINGS, SLOW_STR, TREM_STR, CELLO, VIOLA, CBASS, CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, ENGLISH_HORN,
           HORN, PAN_FLUTE, TRUMPET, TROMBONE, TUBA, SHANAI}


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


# Loudness trim per GM program (dB): the DLS bank plays choirs, ensemble strings, xylophone, celesta ... far quieter than
# cello / horn / bassoon at the same velocity (measured per stem, 2026-11-15), so every part is lifted to a common footing.
TRIM = {CHOIR: 9, OOHS: 10, STRINGS: 7, TREM_STR: 5, SLOW_STR: 3, TUBA: 6, XYLO: 5, CLARINET: 4, CELESTA: 12, GLOCK: 10,
        TROMBONE: 3, TRUMPET: 6, PIZZ: 3, HARP: 3}


def P(s, name, program, *a, bend=False, **kw):
    a = list(a)
    if len(a) > 0: a[0] = a[0] + TRIM.get(program, 0)          # gain_db is the first positional argument after the program
    elif "gain_db" in kw: kw["gain_db"] += TRIM.get(program, 0)
    if bend:
        p = BPart(s, name, program, *a, **kw); s.parts.append(p)
    else:
        p = s.part(name, program, *a, **kw)
    if program in SUSTAIN: sustain_ccs(p)
    return p


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
MARCH = {"D": (LO_CONGA, 96), "T": (HI_BONGO, 72), "t": (LO_BONGO, 58), "k": (MUTE_CONGA, 46), "s": (TAMB, 40)}

# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- call
STORY = [("A5", .5), ("G5", .5), ("F5", 1), ("G5", .5), ("A5", .5), ("C6", 1)]


def cue_call(c):
    """F major, calm. A storyteller's harp and flute, the cello breathes the four-note call figure; at the golden-light
    chime a warm horn + cello sing the call theme (bars 1-2) under God's line, the cello starts the answer ... and Jonah's
    "No way!" cuts it off: the grumpy Jonah theme (bassoon + tuba, D minor) plods in under the pad. The same file plays
    at S08 ("This time I'll go"): its first 11 s carry the figure and the pad."""
    s = Score(c, 64, 4); n = s.bars; total = n * 4; E = end_beats(s)
    horn = P(s, "horn", HORN, -2, .4, lp=4200, human=.01)
    vc = P(s, "cello", CELLO, -1, .4, lp=4500, human=.01)
    padp = P(s, "strings", SLOW_STR, -5, .5, lp=3500)
    vln = P(s, "violins", STRINGS, -10, .5, lp=5000)
    oohs = P(s, "choir oohs", OOHS, -13, .6, lp=4000)
    harp = P(s, "harp", HARP, -6, .45)
    fl = P(s, "flute", FLUTE, -9, .45, human=.01)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1200)
    bsn = P(s, "bassoon (Jonah)", BASSOON, -3, .25, human=.01)
    tuba = P(s, "tuba", TUBA, -8, .25, lp=900)
    pz = P(s, "pizz", PIZZ, -10, .25)
    tc = s.at(c.first("sfx", id="soft_chime")); jb = s.at(c.first("lines", who="jonah"))
    tc = tc if tc is not None else 12.0; jb = jb if jb is not None else total - 6
    # intro: pad, harp, the call figure breathed on the cello, a little flute lilt
    for bar, h in enumerate(["F", "Dm", "Bb", "C"]):
        if bar * 4 >= tc - 1: break
        d_ = 4 if bar < 2 else max(4, tc - bar * 4)        # the last intro chord runs into the statement (no gap)
        pad(padp, bar * 4, h, d_, 44 + 4 * bar, (60, 96)); cb.add(bar * 4, low(chord(h)[0]), d_, 52)
        harp_arp(harp, bar * 4, h, 4, 44)
    mel(vc, .5, call([1, 2]), 56, legato=.98, vib=True, shift=-12)
    oohs.chord(0, [chord("F")[1], chord("F")[3]], 7.5, 34); oohs.ramp(0, 7, 11, 40, 95)
    mel(fl, 8.5, STORY, 58, vib=True)
    for q in (2, 6): pz.add(q, "C4", .3, 40); pz.add(q + .5, "A3", .3, 34)
    # the call theme at the golden light
    mel(horn, tc, call([1, 2]), 78, legato=.97, vib=True)
    mel(vc, tc, call([1, 2]), 68, legato=.98, vib=True, shift=-12)
    pad(padp, tc, "F", 4, 56, (70, 108)); pad(padp, tc + 4, "Bb", 2, 58, (80, 110)); pad(padp, tc + 6, "C", max(2, jb - tc - 6), 58, (80, 110))
    vln.chord(tc, ["A4", "C5", "F5"], 7.5, 44, strum=.05); vln.ramp(tc, tc + 6, 11, 50, 105)
    oohs.chord(tc, [chord("F")[2], chord("F")[3]], 7.5, 42); oohs.ramp(tc, tc + 7, 11, 60, 110)
    cb.add(tc, "F2", 4, 60); cb.add(tc + 4, "Bb2", 2, 58); cb.add(tc + 6, "C3", 2, 58)
    run(harp, tc - .1, scale_run("F3", "C6")[::2], .16, 52, 2.5)
    for p_, b in (("F5", tc + 1), ("C6", tc + 3)): harp.add(b, p_, 3, 42)
    b = tc + 8
    for p_, d in call([3]):
        if b + d <= jb - .25: vc.add(b, p_, d * .96, 70); vc.vibrato(b, d, 28)
        b += d
    # Jonah's "No way!": the grumpy theme interrupts
    pad(padp, jb, "Dm", total - jb, 54, (80, 100)); cb.add(jb, "D2", total - jb, 62)
    tuba.add(jb, "D2", 1.6, 56); tuba.add(jb + 2, "A1", 1.6, 52)
    mel(bsn, jb, jonah([1]), 74, legato=.8)
    pz.add(jb + 1, "D3", .3, 56); pz.add(jb + 3, "A2", .3, 50)
    bsn.add(jb + 4.4, "A3", .4, 66); bsn.add(jb + 5, "D3", max(.6, total - jb - 5.4), 62)
    return s


# ----------------------------------------------------------------------------------------------- runaway
SNEAK = [
    [("D4.", .5), ("F4.", .5), ("A4.", .5), (None, .5), ("G4.", .5), ("F4.", .5), ("E4.", 1)],
    [("D4.", .5), ("F4.", .5), ("A4.", .5), (None, .5), ("Bb4.", .5), ("A4.", .5), ("G4.", 1)],
    [("A3.", .5), ("D4.", .5), ("F4.", .5), (None, .5), ("E4.", .5), ("D4.", .5), ("C#4.", 1)],
    [("D4.", .5), ("E4.", .5), ("F4.", .5), ("G4.", .5), ("A4.", 1), (None, 1)],
]
SNORE = [("A3", 1), ("G3", .5), (None, .5), ("F3", 1.5), (None, .5)]


def cue_runaway(c):
    """Comic tiptoe. Staccato pizzicato sneaks D-F-A while a bassoon creeps the Jonah theme (staccato) underneath,
    wood-block feet on the off-beats, a xylophone climbs the gangplank, a clarinet peeks; the captain's greeting and
    the gulls bring a sea sway (harp, flute); when Jonah dozes off (zzz) the bassoon snores and everything slows to a
    sleepy pad that ends in a low timpani flutter."""
    s = Score(c, 114, 4); n = s.bars; total = n * 4; E = end_beats(s)
    pz = P(s, "pizz tune", PIZZ, -2, .25, human=.006)
    bsn = P(s, "bassoon", BASSOON, -4, .25, human=.006)
    cl = P(s, "clarinet peeks", CLARINET, -7, .3)
    pzb = P(s, "pizz bass", PIZZ, -6, .22)
    xy = P(s, "xylophone", XYLO, -6, .3)
    wb = P(s, "wood blocks", DRUMS, 0, .18, human=.004)
    harp = P(s, "harp", HARP, -8, .45)
    fl = P(s, "flute", FLUTE, -8, .45, human=.01)
    padp = P(s, "pad", SLOW_STR, -9, .5, lp=3500)
    tim = P(s, "timpani", TIMPANI, -8, .3, lp=900)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1000)
    greet = s.at(c.first("lines", who="captain")); gull = s.at(c.first("sfx", id="seagulls")); zzz = s.at(c.first("fx", id="zzz"))
    greet = greet if greet is not None else total * .45; gull = gull if gull is not None else greet + 3
    zzz = zzz if zzz is not None else total - 12
    gp = math.floor(greet / 4) * 4                  # the sea sway starts at the bar of the greeting
    zb = math.ceil(zzz / 4) * 4                     # the snore starts at the next bar line
    for bar in range(n):
        b = bar * 4
        if b >= zb: break
        if b < gp:                                  # tiptoeing along the beach
            mel(pz, b, SNEAK[bar % 4], 76 if bar % 2 == 0 else 70)
            if bar >= 2: mel(bsn, b, jonah([bar % 4 + 1], stacc=True), 58)
            pzb.add(b, "D2", .4, 66); pzb.add(b + 2, "A2", .4, 58)
            for q in range(4): wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 40)
            if bar == 2: cl.add(b + 3.5, "A5", .18, 58); cl.add(b + 3.42, "G#5", .1, 44)     # a peek over the shoulder
        else:                                       # on the ship: the sea sways, the tune relaxes
            h = ["F", "Bb", "Dm", "C"][(bar - gp // 4) % 4]
            harp_arp(harp, b, h, 4, 46, .5)
            pad(padp, b, h, 4, 44, (70, 96)); cb.add(b, low(chord(h)[0]), 4, 52)
            mel(pz, b, SNEAK[bar % 4], 62)
            for q in range(0, 4, 2): wb.add(b + q + .5, LO_WOOD, .2, 32)
            if (bar - gp // 4) % 2 == 1: mel(fl, b, [("A5", 1), ("G5", .5), ("F5", .5), ("G5", 2)], 54, vib=True)
    if gull < zb: run(xy, gull, ["D6", "F6", "A6", "F6"], .125, 54, .3)                       # gulls
    for i, p_ in enumerate(["D4", "F4", "A4", "D5", "F5", "A5"]): xy.add(1.0 + i * .5, p_, .25, 56)   # up the gangplank
    # the snore, then the quiet before the storm
    for bar in range(zb // 4, n):
        b = bar * 4
        pad(padp, b, "Dm", 4, 40, (60, 80)); cb.add(b, "D2", 4, 48)
        mel(bsn, b, SNORE, 52, legato=.9, shift=-12)
        harp.add(b + 2, "A4", 3, 28)
    roll(tim, total - 3.5, total, "D2", 28, 62, .25)
    return s


# ----------------------------------------------------------------------------------------------- storm
OSTI = [["D3", "D3", "A2", "D3", "D3", "F3", "E3", "D3"], ["Bb2", "Bb2", "F3", "Bb2", "A2", "A2", "E3", "A2"],
        ["G2", "G2", "D3", "G2", "G2", "Bb2", "A2", "G2"], ["A2", "A2", "E3", "A2", "C#3", "A2", "E3", "A2"]]
STORM_HARM = ["Dm", "Bb", "Gm", "A"]


def cue_storm(c):
    """D minor, fast and exciting, never horror: a galloping cello / contrabass ostinato, tremolo violins with rising
    waves, horn and trombone punches, timpani and soft cymbal swells; a timpani hit and a crash on each thunder. At S04
    ("It's my fault") it thins to a low pad, a heartbeat on the timpani and the Jonah theme confessing on the
    bassoon; from the captain's order it builds, a timpani roll climbs, and everything lands on one big D minor chord at
    the splash; then only a hush is left."""
    s = Score(c, 144, 4); n = s.bars; total = n * 4; E = end_beats(s)
    vc = P(s, "cello gallop", CELLO, -2, .3, lp=3500, human=.006)
    cbp = P(s, "contrabass", CBASS, -5, .3, lp=1100, human=.006)
    tr = P(s, "tremolo violins", TREM_STR, -7, .5, lp=5500)
    wave = P(s, "string waves", STRINGS, -8, .4, lp=5500, human=.006)
    horn = P(s, "horns", HORN, -4, .4, lp=4000)
    tbn = P(s, "trombone", TROMBONE, -8, .35, lp=2500)
    tim = P(s, "timpani", TIMPANI, -3, .35, lp=1800)
    cym = P(s, "cymbal", DRUMS, -8, .5, lp=7000)
    dr = P(s, "frame drum", DRUMS, -10, .2, lp=3000, human=.005)
    padp = P(s, "low pad", SLOW_STR, -6, .5, lp=2800)
    bsn = P(s, "bassoon (Jonah)", BASSOON, -3, .3, human=.01)
    vcs = P(s, "solo cello", CELLO, -5, .4, lp=3500, human=.01)
    ts = P(s, "trumpet (rising)", TRUMPET, -12, .4, lp=3500)
    s4 = next((sh["t0"] for sh in c.tl["shots"] if sh["id"] == "S04"), None)     # S04 "It's my fault": the music thins
    t_conf = s.at(s4)
    caps = c.all("lines", who="captain"); t_order2 = s.at(caps[-1]) if caps else None     # last captain line: "throw him in"
    t_conf = total * .52 if t_conf is None else t_conf
    t_build = t_order2 if t_order2 is not None else total * .8
    splash = s.at(c.first("sfx", id="splash_big")); splash = splash if splash is not None else total - 2
    cb_ = round(t_conf / 4) * 4; bb_ = round(t_build / 4) * 4; sp_bar = int(splash // 4)
    thunder = [s.at(t) for t in c.all("sfx", id="thunder")]
    for bar in range(n):
        b = bar * 4; h = STORM_HARM[bar % 4]; ps = chord(h)
        if b > splash - .01:                                     # after the splash: a hush
            break
        mid = cb_ <= b < bb_
        if not mid:
            ostinato = OSTI[bar % 4]
            for i, p_ in enumerate(ostinato):
                vc.add(b + i * .5, p_, .42, 78 if i % 4 == 0 else 62); cbp.add(b + i * .5, low(note(p_)) if note(p_) > note("E2") else p_, .42, 60)
            tr.chord(b, [ps[1] + 12, ps[2] + 12], 4.2, 42); tr.ramp(b, b + 4, 11, 80, 110)
            if bar % 2 == 0:
                horn.chord(b, [ps[1], ps[3]], 1.8, 70); tbn.add(b, low(ps[0]), 1.2, 62)
                for k_, p_ in enumerate(scale_run("D4", "D6", ["D", "E", "F", "G", "A", "Bb", "C"])[::2][:8]): wave.add(b + 2 + k_ * .25, p_, .5, 56 + 3 * k_)
            else:
                horn.chord(b + 2, [ps[1], ps[3]], 1.8, 66)
            tim.add(b, "D2" if h in ("Dm", "A") else "G2", 1.6, 84); tim.add(b + 2, "A2" if h == "A" else "D2", 1.4, 66)
            groove(dr, b, "D.tkD.tkD.tkD.tk", .25, FRAME, .8)
            if bar % 4 == 3: roll(tim, b + 3, b + 4, "A2", 54, 84, .2)
            if bar % 4 == 0 and bar > 0: cym.add(b, CRASH, 3, 44)
        else:                                                    # S04: thin, a heartbeat, Jonah confesses
            pad(padp, b, "Dm" if bar % 2 == 0 else "Gm", 4, 52, (70, 100)); cbp.add(b, low(ps[0]), 4, 56)
            for q in range(4): tim.add(b + q, "D2", .5, 34 + 6 * (q % 2 == 0))
    # the confession: the Jonah theme on the bassoon + a low solo cello answer
    if cb_ < bb_:
        mel(bsn, cb_ + 1, jonah([1, 2, 3, 4], scale=1.0), 70, legato=.9)
        mel(vcs, cb_ + 1, [("A3", 4), ("G3", 4), ("F3", 4), ("D3", 3)], 52, legato=.98, vib=True)
    # the build to the splash: climbing trumpet + timpani roll + cymbal swell
    b0 = bb_; roll(tim, max(b0, splash - 8), splash, "D2", 36, 100, .2)
    for i, p_ in enumerate(["D4", "F4", "A4", "D5", "F5", "A5"]): ts.add(splash - 6 + i, p_, 1, 54 + 4 * i)
    ts.ramp(splash - 6, splash, 11, 70, 120)
    for t_ in thunder:
        if t_ is not None and t_ < splash - 1: tim.add(t_, "D2", 2, 108); cym.add(t_, CRASH, 3, 66); horn.chord(t_, [chord("Dm")[0], chord("Dm")[2]], 1.5, 90)
    # the big moment at the splash, then the hush
    ps = chord("Dm"); tim.add(splash, "D2", 3, 118); cym.add(splash, CRASH, 4, 78)
    horn.chord(splash, [ps[1], ps[2]], 3.5, 100); tbn.add(splash, "D2", 3, 90); vc.chord(splash, [ps[0], ps[1]], 3.5, 96)
    tr.chord(splash, [ps[2] + 12, ps[3] + 12], 3, 90); wave.chord(splash, [ps[2], ps[3] + 12], 3, 90)
    padp.chord(splash, ps[1:], total - splash + 2, 60); padp.ramp(splash, splash + 3, 11, 110, 50, .6)
    cbp.add(splash, "D2", total - splash + 1, 70)
    return s


# ----------------------------------------------------------------------------------------------- deep
DEEP_HARM = ["Fmaj7", "Dm7", "Bb", "C"]
DEEP_HARP = ["A4", "C5", "G4", "D5", "F4", "E5", "C5", "A4"]


def cue_deep(c):
    """Underwater, hushed: after the splash a very low pad and a soft choir 'oo' sink through F / D minor chords, a
    single harp note falls like a bubble every two beats, glock drops far away, a cello 'whale call' slides up and
    down. At the gulp a bassoon sinks a few semitones and is gone; after that only the pad and a lone harp remain."""
    s = Score(c, 52, 4); n = s.bars; total = n * 4; E = end_beats(s)
    padp = P(s, "low pad", SLOW_STR, -3, .6, lp=1800)
    ch = P(s, "choir oo", CHOIR, -10, .7, lp=2500)
    oohs = P(s, "oohs", OOHS, -14, .7, lp=2200)
    harp = P(s, "harp (bubbles)", HARP, -6, .6, lp=3500)
    gl = P(s, "glock (far)", GLOCK, -18, .7, lp=4500)
    whale = P(s, "cello whale call", CELLO, -8, .6, lp=1800, bend=True)
    cb = P(s, "contrabass", CBASS, -8, .4, lp=700)
    bsn = P(s, "bassoon", BASSOON, -6, .4, lp=1800, bend=True)
    tim = P(s, "timpani (swell)", TIMPANI, -14, .5, lp=500)
    gulp = s.at(c.first("sfx", id="gulp")); burp = s.at(c.first("sfx", id="burp"))
    for bar in range(n):
        b = bar * 4; h = DEEP_HARM[bar % 4]; ps = chord(h)
        pad(padp, b, h, 4, 44, (50, 84)); cb.add(b, low(ps[0]), 4, 46)
        ch.chord(b, [ps[1], ps[2], ps[3]], 4.3, 30); ch.ramp(b, b + 3.5, 11, 55, 100, .8)
        if bar % 2 == 0: oohs.chord(b, [ps[2] + 12], 8, 26)
        for q in range(0, 4, 2):
            k = (bar * 2 + q // 2) % len(DEEP_HARP); harp.add(b + q, DEEP_HARP[k], 3, 40 + (6 if q == 0 else 0))
        if bar % 2 == 1: gl.add(b + 1.5, ["E6", "C6", "A6", "G6"][bar // 2 % 4], 3, 30)
        if bar % 4 == 2: tim.add(b, "D2", 4, 24)
    # whale calls: a long slide up then down, twice
    for wb in (4.0, 17.0):
        if wb + 7 < total:
            whale.add(wb, "D3", 6, 56); whale.glide(wb, wb + 2.5, -3, 4, .6); whale.glide(wb + 3, wb + 6, 4, -2, 1.2); whale.vibrato(wb, 6, 26)
    # the gulp: the bassoon sinks
    if gulp is not None:
        bsn.add(gulp - .25, "G3", 1.4, 64); bsn.glide(gulp + .1, gulp + 1.2, 0, -5, 1.1); bsn.bend(gulp + 1.3, 0)
    return s


# ----------------------------------------------------------------------------------------------- prayer
def cue_prayer(c):
    """F major, hushed. The call theme is heard from far away on a muted horn and a breath of choir (God is near);
    each time a solo cello answers it. When the prayer glows (prayer_glow) the cello sings the whole call theme over
    a warm string pad and choir, a harp turns the page, and the cue settles on F."""
    s = Score(c, 60, 4); n = s.bars; total = n * 4; E = end_beats(s)
    horn = P(s, "horn (far)", HORN, -7, .6, lp=3000, human=.012)
    vc = P(s, "solo cello", CELLO, -1, .4, lp=4200, human=.01)
    padp = P(s, "strings", SLOW_STR, -6, .5, lp=3000)
    vln = P(s, "violins", STRINGS, -11, .6, lp=4500)
    ch = P(s, "choir", CHOIR, -11, .65, lp=3500)
    oohs = P(s, "oohs", OOHS, -14, .65, lp=3500)
    harp = P(s, "harp", HARP, -7, .5)
    fl = P(s, "flute", FLUTE, -10, .5, human=.01)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1000)
    cel = P(s, "celesta", CELESTA, -17, .6)
    tg = s.at(c.first("fx", id="prayer_glow")); tg = tg if tg is not None else total * .55
    tg = round(tg / 4) * 4; tg = min(max(tg, 8), total - 8)
    for bar in range(n):
        b = bar * 4; h = ["F", "Dm", "Bb", "C"][bar % 4]
        if b >= total - 4: h = "F"
        ps = chord(h); pad(padp, b, h, 4, 38 if b < tg else 50, (60, 90) if b < tg else (80, 108)); cb.add(b, low(ps[0]), 4, 44 if b < tg else 54)
        harp_arp(harp, b, h, 4, 36 if b < tg else 46, 1.0 if b < tg else .5)
    # before the glow: the far call (bars 1-2), the cello's answer (bars 3-4), again a little higher
    b0 = 0.5
    mel(horn, b0, call([1, 2]), 46, legato=.97)
    oohs.chord(b0, [chord("F")[2], chord("F")[3] + 12], 7.5, 28)
    mel(vc, b0 + 8, call([3]) + [("F3", max(1, tg - b0 - 12.5))], 60, legato=.98, vib=True, shift=-12)
    mel(fl, 2.0, [("C6", 2), ("A5", 1), ("G5", 3)], 36, vib=True)
    # the glow: the cello sings the whole theme, choir and violins swell
    mel(vc, tg, call([1, 2, 3, 4]), 76, legato=.98, vib=True, shift=-12)
    mel(horn, tg + 8, call([3, 4]), 54, legato=.97)
    ch.chord(tg, [chord("F")[1], chord("F")[2], chord("F")[3]], 14, 40); ch.ramp(tg, tg + 8, 11, 60, 110)
    vln.chord(tg, ["A4", "C5", "F5"], 14, 44, strum=.06); vln.ramp(tg, tg + 8, 11, 55, 108)
    run(harp, tg - .1, scale_run("F3", "A5")[::2], .2, 48, 2.5)
    for i, p_ in enumerate(["C7", "A6", "F6"]): cel.add(tg + 3 + i * 1.5, p_, 2, 40)
    cel.add(total - 4, "A6", 3, 34)
    return s


# ----------------------------------------------------------------------------------------------- shore
SHORE_TUNE = [
    [("A4", .5), ("C5", .5), ("D5", 1), ("C5", .5), ("A4", .5), ("F4", 1)],
    [("G4", .5), ("A4", .5), ("Bb4", 1), ("A4", .5), ("G4", .5), ("C5", 1)],
    [("A4", .5), ("C5", .5), ("D5", 1), ("F5", .5), ("D5", .5), ("C5", 1)],
    [("Bb4", .5), ("A4", .5), ("G4", 1), ("F4", 2)],
]
SHORE_HARM = ["F", "C", "Dm", "Bb"]


def cue_shore(c):
    """F major, bright morning. A hushed sea dawn (flute rising over a pad and harp, a soft timpani roll while the fish
    gulps up its courage), then at the "pfft" a trombone slides down with a cartoon whoop and a xylophone tumble, and the
    beach tune bursts in: flute over plucked nylon strings, pizzicato bass, glock and a light shaker."""
    s = Score(c, 120, 4); n = s.bars; total = n * 4; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -3, .4, human=.008)
    ny = P(s, "nylon pluck", NYLON, -5, .3)
    pzb = P(s, "pizz bass", PIZZ, -6, .22)
    harp = P(s, "harp", HARP, -7, .45)
    gl = P(s, "glock", GLOCK, -11, .5)
    sh = P(s, "shaker + wood", DRUMS, -4, .18, human=.004)
    padp = P(s, "pad", SLOW_STR, -8, .5, lp=3800)
    tim = P(s, "timpani", TIMPANI, -11, .3, lp=900)
    tb = P(s, "trombone slide", TROMBONE, -3, .3, lp=3500, bend=True)
    xy = P(s, "xylophone", XYLO, -5, .3)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1000)
    pop = s.at(c.first("sfx", id="spit_pop")); pop = pop if pop is not None else total * .5
    pb = round(pop)
    # before the pop: dawn
    for bar in range(int(pb // 4) + 1):
        b = bar * 4
        if b >= pb - .5: break
        h = ["F", "Bb", "F", "C"][bar % 4]; pad(padp, b, h, min(4, pb - b), 38 + 4 * bar, (55, 90)); cb.add(b, low(chord(h)[0]), min(4, pb - b), 44)
        harp_arp(harp, b, h, min(4, pb - b), 38, 1.0)
    mel(fl, 0.5, [("C5", 2), ("F5", 1), ("A5", 1), ("C6", 3)], 50, vib=True)
    roll(tim, max(0, pb - 5), pb - .1, "F2", 26, 70, .25)
    # the pop: slide, whoop, tumble
    tb.add(pb - .05, "C5", 1.6, 86); tb.glide(pb - .05, pb + 1.4, 3, -9, .8); tb.vibrato(pb, 1.4, 20)
    for i, p_ in enumerate(["C6", "A5", "F5", "D5", "C5", "A4", "F4"]): xy.add(pb + .15 + i * .14, p_, .3, 74 - 2 * i)
    sh.add(pb, CRASH, 2.5, 52)
    # the beach tune
    q0 = pb + 1.5; bar_i = 0; b = q0
    while b + 4 <= total + .01:
        h = SHORE_HARM[bar_i % 4]; ps = chord(h)
        mel(fl, b, SHORE_TUNE[bar_i % 4], 74 if bar_i < 4 else 70, vib=True)
        if bar_i % 4 in (0, 2): mel(gl, b, SHORE_TUNE[bar_i % 4], 40, shift=12)
        for j in range(8): ny.add(b + j * .5, ps[[1, 2, 3, 2, 1, 2, 3, 2][j]], .45, 58 if j % 4 == 0 else 44)
        pzb.add(b, low(ps[0]), .4, 66); pzb.add(b + 2, ps[1] - 12 if ps[1] - 12 >= note("C2") else ps[1], .4, 58)
        pad(padp, b, h, 4, 40, (80, 96)); cb.add(b, low(ps[0]), 4, 50)
        for q in range(8): sh.add(b + q * .5, SHAKER, .2, 30 if q % 2 == 0 else 42)
        b += 4; bar_i += 1
    # land the last bar on F
    if b < total: fl.add(b, "F5", total - b + 1, 64)
    return s


# ----------------------------------------------------------------------------------------------- nineveh
HIJAZ = ["D", "Eb", "F#", "G", "A", "Bb", "C"]
NINEVEH = [
    [("D5", 1), ("Eb5", .5), ("F#5", .5), ("G5", 1.5), ("F#5", .5)],
    [("Eb5", 1), ("D5", .5), ("C5", .5), ("D5", 2)],
    [("A5", 1), ("G5", .5), ("F#5", .5), ("Eb5", 1), ("F#5", 1)],
    [("G5", 1.5), ("F#5", .5), ("Eb5", 1), ("D5", 1)],
]


def cue_nineveh(c):
    """D hijaz (D Eb F# G A Bb C), a broad march: frame drums and bongos on the beat, tambourine, a drone on D (contrabass
    and tuba), a reed (shanai) sings the city tune, a qanun (koto) tremolos the cadences, horns call at the gate."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4; E = end_beats(s)
    reed = P(s, "reed (shanai)", SHANAI, -3, .4, lp=4200, human=.01)
    reed2 = P(s, "oboe double", OBOE, -10, .4, lp=3500)
    qn = P(s, "qanun (koto)", KOTO, -6, .3, human=.006)
    dr = P(s, "frame drums", DRUMS, -4, .2, lp=3500, human=.005)
    cb = P(s, "contrabass", CBASS, -6, .3, lp=1000)
    tuba = P(s, "tuba", TUBA, -9, .25, lp=900)
    horn = P(s, "horns", HORN, -6, .4, lp=3800)
    padp = P(s, "strings", SLOW_STR, -9, .5, lp=3500)
    pz = P(s, "pizz", PIZZ, -8, .22)
    for bar in range(n):
        b = bar * 4
        groove(dr, b, "D.tkD.tTD.tkDktT" if bar % 4 != 3 else "D.tkD.tTDtDtDDDD", .25, MARCH, .95)
        groove(dr, b, "s.s.s.s.", .5, MARCH, .8)
        cb.add(b, "D2", 1.8, 62); cb.add(b + 2, "A2", 1.8, 54); tuba.add(b, "D2", 1.0, 56); tuba.add(b + 2, "D2", 1.0, 50)
        pz.add(b + 1, "A3", .3, 52); pz.add(b + 3, "F#3", .3, 46)
        pad(padp, b, "D", 4, 40, (70, 96) if bar else (55, 90))
        ph = NINEVEH[bar % 4] if bar >= 1 or n < 3 else [(None, 4)]
        mel(reed, b, ph, 76, vib=True, legato=.95); mel(reed2, b, ph, 56, legato=.95)
        if bar % 2 == 0: qn.add(b, "D5", .5, 50)
        if bar % 4 == 3: qn.tremolo(b + 2, note("D5"), 2, 54, 11)
    horn.chord(0, [chord("D")[1], chord("D")[2]], 1.6, 72); horn.add(total - 4, "A3", 1.5, 70)
    for p_ in ("D4", "A4"): qn.add(total - 1, p_, 1.0, 62)
    return s


# ----------------------------------------------------------------------------------------------- repent
SORRY = [("A4", 2), ("G4", 1), ("F4", 1), ("E4", 2), ("D4", 2)]


def cue_repent(c):
    """The whole city says sorry: a hushed D minor (low strings, choir 'oo', a sorrowful cello line) swells bar by bar;
    when the narrator tells how God saw it, it turns to F major, the choir opens, the harp climbs; at the chime of
    forgiveness the horn sings the call figure over a golden string swell with celesta, and it settles on F."""
    s = Score(c, 72, 4); n = s.bars; total = n * 4; E = end_beats(s)
    padp = P(s, "strings", SLOW_STR, -4, .5, lp=3500)
    vln = P(s, "violins", STRINGS, -9, .55, lp=5200)
    ch = P(s, "choir", CHOIR, -8, .65, lp=3800)
    oohs = P(s, "oohs", OOHS, -11, .65, lp=3800)
    vc = P(s, "cello", CELLO, -2, .4, lp=4200, human=.01)
    harp = P(s, "harp", HARP, -7, .45)
    horn = P(s, "horn", HORN, -4, .4, lp=4000)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1100)
    tim = P(s, "timpani", TIMPANI, -10, .3, lp=900)
    cel = P(s, "celesta", CELESTA, -15, .6)
    fl = P(s, "flute", FLUTE, -9, .45, human=.01)
    t_turn = s.at(c.first("lines", who="narrator")); t_ch = s.at(c.first("sfx", id="soft_chime"))
    t_turn = t_turn if t_turn is not None else total * .45; t_ch = t_ch if t_ch is not None else total - 6
    t_turn = round(t_turn / 4) * 4; t_ch = max(t_ch, t_turn + 4)
    minor = ["Dm", "Gm", "Bb", "A"]; major = ["F", "Bb", "Gm", "C"]
    for bar in range(n):
        b = bar * 4
        if b < t_turn:
            h = minor[bar % 4]; v = 40 + 4 * bar; ps = chord(h)
            pad(padp, b, h, 4, v, (60, 92)); cb.add(b, low(ps[0]), 4, 50)
            ch.chord(b, [ps[1], ps[2]], 4.3, 28 + 3 * bar); ch.ramp(b, b + 3.6, 11, 55, 100)
            if bar: tim.add(b, "D2", 2, 30 + 4 * bar)
            harp.add(b + 1, ps[2], 3, 34); harp.add(b + 3, ps[3] + 12, 3, 30)
        else:
            k = bar - t_turn // 4; h = major[k % 4] if b < total - 4 else "F"; ps = chord(h)
            pad(padp, b, h, 4, 54 + 3 * k, (82, 108)); cb.add(b, low(ps[0]), 4, 58)
            ch.chord(b, [ps[1], ps[2], ps[3]], 4.3, 44 + 3 * k); ch.ramp(b, b + 3.5, 11, 78, 112)
            oohs.chord(b, [ps[2] + 12], 4.3, 36)
            vln.chord(b, [ps[1] + 12, ps[3] + 12], 4.3, 42 + 3 * k, strum=.05); vln.ramp(b, b + 3.5, 11, 70, 108)
            harp_arp(harp, b, h, 4, 46, .5)
    # the sorrowful line (cello) while they say sorry, then the flute's lift
    mel(vc, 0.5, SORRY, 68, legato=.98, vib=True)
    mel(vc, 8.5, [("C4", 2), ("Bb3", 1), ("A3", 1), ("G3", 4)], 66, legato=.98, vib=True)
    mel(fl, t_turn + .5, [("F5", 1.5), ("A5", .5), ("C6", 2)], 56, vib=True)
    # forgiveness: the call figure on the horn, golden celesta, the timpani warms the cadence
    mel(horn, t_ch, call([1, 2]), 74, legato=.97, vib=True)
    mel(vc, t_ch, call([1, 2]), 66, legato=.98, vib=True, shift=-12)
    run(cel, t_ch, ["F6", "A6", "C7", "A6", "F6", "C7"], .25, 36, 2.5)
    roll(tim, t_ch + 4, total - .5, "F2", 30, 62, .25)
    horn.add(total - 4, "F4", 4.5, 66); vc.add(total - 4, "F3", 4.5, 64)
    return s


# ----------------------------------------------------------------------------------------------- sulk
def cue_sulk(c):
    """D minor, Jonah at his grumpiest: the whole Jonah theme stomps on the bassoon over a plodding tuba and pizzicato, a
    sour clarinet counter-line sighs a half tone flat; a "pffft" slide on the clarinet when the steam comes out of his
    ears; a final low grumble."""
    s = Score(c, 88, 4); n = s.bars; total = n * 4; E = end_beats(s)
    bsn = P(s, "bassoon (Jonah)", BASSOON, -1, .25, human=.008)
    tuba = P(s, "tuba", TUBA, -4, .25, lp=1000, human=.006)
    cl = P(s, "sour clarinet", CLARINET, -5, .3, bend=True)
    pz = P(s, "pizz", PIZZ, -6, .22)
    wb = P(s, "wood blocks", DRUMS, -2, .18, human=.005)
    padp = P(s, "pad", SLOW_STR, -9, .5, lp=2800)
    tim = P(s, "timpani", TIMPANI, -9, .3, lp=800)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1000)
    steam = s.at(c.first("fx", id="steam"))
    th = [1, 2, 3, 4]
    for k in range(n):
        b = k * 4; bar = th[k % 4]; hs = JONAH_HARM[bar]
        for i, h in enumerate(hs):
            hb = b + i * 4 / len(hs); ps = chord(h)
            tuba.add(hb, low(ps[0]) if low(ps[0]) >= note("E1") else ps[0], 1.2, 62); tuba.add(hb + 2 / len(hs) * 1.0 + 1, low(ps[0]), .8, 54)
            pad(padp, hb, h, 4 / len(hs), 38, (70, 90))
            cb.add(hb, low(ps[0]), 4 / len(hs), 50)
        for q in range(4):
            pz.add(b + q + .5, "D3", .2, 44); wb.add(b + q, LO_WOOD, .2, 40 if q % 2 == 0 else 28)
        if k % 2 == 0: tim.add(b, "D2", 1.5, 54)
    mel(bsn, 0, jonah(th), 80, legato=.8)
    # the sour clarinet: a flat, sighing counter-line
    mel(cl, 2.0, [("A4", 1), ("Ab4", 1)], 56); mel(cl, 6.0, [("G4", 1), ("Gb4", 1), ("F4", 1)], 56)
    cl.glide(2.9, 3.9, 0, -1.5); cl.glide(6.9, 7.9, 0, -1.5)
    if steam is not None:                                       # "pffft" from the ears
        cl.add(steam, "C6", 1.2, 80); cl.glide(steam, steam + 1.2, 0, -10, .8); cl.bend(steam + 1.4, 0)
        wb.add(steam, HI_WOOD, .2, 50)
    tuba.add(total - 1, "D2", 1.2, 64)
    return s


# ----------------------------------------------------------------------------------------------- plant
PLANT_TUNE = [
    [("F5", .5), ("A5", .5), ("C6", 1), ("A5", .5), ("F5", .5), ("G5", 1)],
    [("A5", .5), ("C6", .5), ("D6", 1), ("C6", .5), ("A5", .5), ("F5", 1)],
]
WORM = [("E4.", .25), ("F4.", .25), ("E4.", .25), ("Eb4.", .25), ("E4.", .25), ("F4.", .25), ("G4.", .5)]


def cue_plant(c):
    """F major, playful. A harp climbs as the little plant grows, a xylophone / flute tune hops, glock sparkles; a wiggly
    clarinet is the worm; at the munch the tuba chomps and a trombone drops the plant's "wah-wah-wah-waaah" droop;
    the sun scorches: shimmering high strings, a limp bassoon echo of the Jonah theme, a last wah-wah, and the cue
    hangs open on C for the mercy to answer."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4; E = end_beats(s)
    harp = P(s, "harp (grow)", HARP, -3, .4)
    xy = P(s, "xylophone", XYLO, -6, .3)
    fl = P(s, "flute", FLUTE, -5, .4, human=.008)
    gl = P(s, "glock", GLOCK, -12, .5)
    pz = P(s, "pizz bass", PIZZ, -6, .22)
    wb = P(s, "wood blocks", DRUMS, -1, .18, human=.004)
    cl = P(s, "clarinet (worm)", CLARINET, -4, .3, human=.006)
    tuba = P(s, "tuba (munch)", TUBA, -4, .25, lp=1200)
    tbn = P(s, "trombone (wah)", TROMBONE, -3, .3, lp=3000, bend=True)
    padp = P(s, "pad", SLOW_STR, -9, .5, lp=3500)
    tr = P(s, "heat shimmer", TREM_STR, -10, .6, lp=6000)
    bsn = P(s, "bassoon (Jonah)", BASSOON, -4, .3, bend=True)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1000)
    grow = s.at(c.first("sfx", id="grow_whoosh")); munch = s.at(c.first("sfx", id="munch")); sun = s.at(c.first("fx", id="sun_scorch"))
    grow = grow if grow is not None else 0.5; munch = munch if munch is not None else total * .5; sun = sun if sun is not None else total * .78
    mb = math.ceil((munch + 1.5) / 4) * 4; sb = round(sun / 4) * 4
    # the grow figure: harp climbs the F major scale, three rising bursts
    for k, (lo, hi) in enumerate((("F3", "C5"), ("C4", "A5"), ("F4", "F6"))):
        run(harp, grow + k * 3.2, scale_run(lo, hi), .16, 50 + 4 * k, 2.2)
    for i, p_ in enumerate(["C6", "E6", "G6", "A6", "C7"]): gl.add(grow + 7 + i * .35, p_, 2, 38)
    cb_h = ["F", "Bb", "F", "C"]
    for bar in range(n):
        b = bar * 4; ps = chord(cb_h[bar % 4])
        if b < mb - 4 + .1 and b >= (grow // 4) * 4 + 8:                       # the hopping tune after the growth
            mel(xy, b, PLANT_TUNE[bar % 2], 68); mel(fl, b, PLANT_TUNE[bar % 2], 56, vib=True)
        if b < mb - 4 + .1:
            pz.add(b, low(ps[0]), .4, 64); pz.add(b + 2, ps[1] - 12 if ps[1] - 12 >= note("C2") else ps[1], .4, 56)
            for q in range(4): wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 32)
        if b < sb:                                                    # the pad never drops out; it turns sad after the munch
            h = cb_h[bar % 4] if b < mb - 4 + .1 else ["Dm", "Gm", "Bb", "C"][bar % 4]
            pad(padp, b, h, 4, 38 if b < mb - 4 + .1 else 42, (60, 90)); cb.add(b, low(chord(h)[0]), 4, 48)
    # the worm wiggles, then the munch
    for wbeat in (int(grow) + 8, int(munch) - 6):
        if wbeat > 0 and wbeat + 3 < munch: mel(cl, wbeat, WORM, 62)
    for i in range(4): tuba.add(munch + i * .5, "F2" if i % 2 == 0 else "C2", .3, 76); wb.add(munch + i * .5, LO_WOOD, .15, 56)
    # the droop: wah - wah - wah - waaah
    d0 = munch + 2.5
    for i, (p_, d) in enumerate((("C5", .75), ("A4", .75), ("F4", .75), ("D4", 2.5))):
        tbn.add(d0 + i * .9, p_, d, 78 - 4 * i)
        if i < 3: tbn.glide(d0 + i * .9 + .3, d0 + i * .9 + .9, 0, -2.0, 1.0); tbn.bend(d0 + i * .9 + .95, 0)
    tbn.glide(d0 + 2.7 + .4, d0 + 2.7 + 2.9, 0, -6, 1.3)
    # the sun: shimmering strings, the limp Jonah tune, a last wah-wah, open on C
    for bar in range(sb // 4, n):
        b = bar * 4; h = "Dm" if b < total - 4 else "C"; ps = chord(h)
        pad(padp, b, h, 4, 44, (70, 96)); cb.add(b, low(ps[0]), 4, 54)
        tr.chord(b, [ps[2] + 12, ps[3] + 12], 4.3, 40); tr.ramp(b, b + 3, 11, 60, 100)
    mel(bsn, sb + 1, [("D3", 1), ("D3", .5), ("D3", .5), ("F3", 1), ("D3", 2)], 62, legato=.8); bsn.glide(sb + 1 + 6, sb + 1 + 7, 0, -3, 1.2); bsn.bend(sb + 8.2, 0)
    w0 = total - 4.5
    for i, (p_, d) in enumerate((("A4", .7), ("F4", .7), ("D4", 1.6))):
        tbn.add(w0 + i * .9, p_, d, 66); tbn.glide(w0 + i * .9 + .3, w0 + i * .9 + .9, 0, -2.0 if i < 2 else -4.0, 1.0)
    return s


# ----------------------------------------------------------------------------------------------- mercy
def cue_mercy(c):
    """F major, the heart of the story. While God speaks, the call theme in full: horn and cello over strings, choir
    and harp. At the heart glow the gentle Jonah theme (F major, bassoon + clarinet) joins the call theme in the horns:
    the two tunes together. The cue ends on a held F chord with a harp roll and celesta."""
    s = Score(c, 66, 4); n = s.bars; total = n * 4; E = end_beats(s)
    horn = P(s, "horn", HORN, -1, .4, lp=4200, human=.01)
    vc = P(s, "cello", CELLO, -1, .4, lp=4500, human=.01)
    padp = P(s, "strings", SLOW_STR, -4, .5, lp=3500)
    vln = P(s, "violins", STRINGS, -8, .55, lp=5200)
    ch = P(s, "choir", CHOIR, -9, .65, lp=3800)
    oohs = P(s, "oohs", OOHS, -12, .65, lp=3800)
    harp = P(s, "harp", HARP, -6, .45)
    bsn = P(s, "bassoon (Jonah, gentle)", BASSOON, -3, .3, human=.01)
    cl = P(s, "clarinet", CLARINET, -8, .35, human=.01)
    fl = P(s, "flute", FLUTE, -8, .45, human=.01)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1100)
    tim = P(s, "timpani", TIMPANI, -11, .3, lp=900)
    cel = P(s, "celesta", CELESTA, -14, .6)
    th = s.at(c.first("fx", id="heart_glow")); th = round(th / 4) * 4 if th is not None else 16
    th = min(max(th, 12), total - 8)
    k = th / 16.0                                                # the call theme in full fills the bars before the glow
    mel(horn, 0.3, call([1, 2, 3, 4], k), 76, legato=.97, vib=True)
    mel(vc, 0.3, call([1, 2, 3, 4], k), 68, legato=.98, vib=True, shift=-12)
    for j, bar in enumerate([1, 2, 3, 4]):
        harm_at(lambda bt, h, d: (pad(padp, bt, h, d + .1, 52 + 2 * j, (65 if j == 0 else 84, 108)),
                                  cb.add(bt, low(chord(h)[0]), d, 56)), 0.3 + j * 4 * k, CALL_HARM[bar], 4 * k)
        harp_arp(harp, 0.3 + j * 4 * k, CALL_HARM[bar][0], 4 * k, 40 + 2 * j, 1.0)
    ch.chord(0.3, [chord("F")[1], chord("F")[2], chord("F")[3]], th, 40); ch.ramp(0.3, th - 2, 11, 45, 105)
    vln.chord(th - 6, ["A4", "C5", "F5"], 6, 44, strum=.06); vln.ramp(th - 6, th, 11, 50, 110)
    # the two tunes together: call theme on the horns, the gentle Jonah theme (major) on bassoon + clarinet
    mel(horn, th, call([1, 2, 3, 4]), 72, legato=.97, vib=True)
    mel(bsn, th, jonah([1, 2, 3, 4], major=True), 72, legato=.95)
    mel(cl, th, jonah([1, 2, 3, 4], major=True), 54, legato=.95, shift=12)
    mel(vc, th, call([1, 2, 3, 4]), 62, legato=.98, vib=True, shift=-12)
    for j, bar in enumerate([1, 2, 3, 4]):
        harm_at(lambda bt, h, d: (pad(padp, bt, h, d + .1, 58 + 2 * j, (88, 112)),
                                  cb.add(bt, low(chord(h)[0]), d, 60)), th + j * 4, CALL_HARM[bar], 4)
        harp_arp(harp, th + j * 4, CALL_HARM[bar][0], 4, 46, .5)
        ch.chord(th + j * 4, [chord(CALL_HARM[bar][0])[1], chord(CALL_HARM[bar][0])[2], chord(CALL_HARM[bar][0])[3]], 4.3, 46 + 2 * j)
        oohs.chord(th + j * 4, [chord(CALL_HARM[bar][-1])[2] + 12], 4.3, 36)
    mel(fl, th + 8, [("C6", 2), ("A5", 1), ("G5", 1), ("A5", 2), ("F5", 2)], 54, vib=True)
    # the end: a held F chord, harp roll, celesta, a soft timpani roll
    fe = th + 16
    if fe < total + .5:
        ps = chord("F"); pad(padp, fe, "F", total - fe + 1, 58, (100, 115)); cb.add(fe, "F2", total - fe + 1, 62)
        horn.chord(fe, [ps[1], ps[2]], total - fe + 1, 66); horn.vibrato(fe, total - fe, 24)
        vc.chord(fe, ["F3", "C4"], total - fe + 1, 62); ch.chord(fe, ps[1:], total - fe + 1, 56)
        vln.chord(fe, ["A4", "C5", "F5"], total - fe + 1, 50, strum=.05)
        run(harp, fe, [ps[0], ps[1], ps[2], ps[3], ps[1] + 24, ps[2] + 24, ps[3] + 24], .12, 56, 4)
        for i, p_ in enumerate(["F6", "A6", "C7"]): cel.add(fe + .5 + i * .4, p_, 3, 38)
        roll(tim, fe - 1, fe, "F2", 28, 56, .2); tim.add(fe, "F2", 4, 60)
    return s


# =============================================================================================== loop sections
VAMP = {"call": ("Dm", "bed"), "runaway": ("Dm", "tiptoe"), "storm": ("Dm", "hush"), "deep": ("Dm", "deep"),
        "prayer": ("F", "bed"), "shore": ("F", "bells"), "nineveh": ("D", "march"), "repent": ("F", "choir"),
        "sulk": ("Dm", "plod"), "plant": ("C", "bed"), "mercy": ("F", "choir")}


def arp_steps(s): return (s.bpb * 2, .5) if s.bpb in (3, 4) else (s.bpb, 1.0)


def add_vamp(s, chord_name, style):
    """After the cadence: identical repeats of >= VAMP_MIN_SEC (whole bars, no humanising). See music_ruth.py."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((STRETCH * s.span + XFADE + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    quiet = style in ("hush", "deep", "tiptoe", "plod")
    padp = P(s, "vamp pad", SLOW_STR, -6, .5, lp=3500 if style not in ("deep", "hush") else 2000, **v)
    cb = P(s, "vamp bass", CBASS, -10, .3, lp=1100, **v)
    harp = P(s, "vamp harp", HARP, -8, .45, **v)
    extra = {}
    if style == "tiptoe":
        extra["pz"] = P(s, "vamp pizz", PIZZ, -6, .25, **v); extra["wb"] = P(s, "vamp blocks", DRUMS, -8, .18, **v)
    if style == "plod":
        extra["pz"] = P(s, "vamp pizz", PIZZ, -7, .25, **v); extra["tb"] = P(s, "vamp tuba", TUBA, -12, .25, lp=900, **v)
        extra["wb"] = P(s, "vamp blocks", DRUMS, -8, .18, **v)
    if style == "march":
        extra["dr"] = P(s, "vamp drums", DRUMS, -11, .2, lp=3200, **v); extra["tb"] = P(s, "vamp tuba", TUBA, -13, .25, lp=900, **v)
    if style == "bells": extra["cel"] = P(s, "vamp celesta", CELESTA, -16, .6, **v)
    if style == "choir":
        extra["oohs"] = P(s, "vamp oohs", OOHS, -14, .6, lp=4000, **v); extra["ch"] = P(s, "vamp choir", CHOIR, -17, .6, lp=3500, **v)
    for p_ in [padp, cb, harp] + list(extra.values()): p_.vamp = True
    ps = chord(chord_name); steps, st = arp_steps(s); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 34 if quiet else 46); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 44 if quiet else 48)
        if style == "choir":
            extra["oohs"].chord(b, [ps[1] + 12, ps[3]], Lb + .3, 40); extra["oohs"].cc(b, 11, 92)
            extra["ch"].chord(b, ps[1:], Lb + .3, 34); extra["ch"].cc(b, 11, 92)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "bells", "choir"):
                for j in range(steps): harp.add(bb + j * st, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.4, 44 if j else 50)
            if style in ("deep", "hush"):
                harp.add(bb, ps[[3, 2, 1, 2][bar % 4]] + 12, 3, 32); harp.add(bb + 2, ps[1] + 24, 3, 24)
            if style == "tiptoe":
                for q, idx in enumerate([0, 1, 3, 1]): extra["pz"].add(bb + q, ps[idx], .2, 50)
                for q in range(4): extra["wb"].add(bb + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 28)
            if style == "plod":
                for q in range(0, bpb, 2): extra["tb"].add(bb + q, low(ps[0]), 1.2, 44)
                for q in range(bpb): extra["pz"].add(bb + q + .5, ps[1], .2, 36); extra["wb"].add(bb + q, LO_WOOD, .15, 26)
                harp.add(bb, ps[3] + 12, 3, 28)
            if style == "march":
                groove(extra["dr"], bb, "D.tkD.tTD.tkDktT", .25, MARCH, .55)
                for q in range(0, bpb, 2): extra["tb"].add(bb + q, low(ps[0]), 1.0, 40)
                harp.add(bb, ps[3] + 12, 3, 30)
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
            if me.STEM_REPORT: print(f"    stem {p_.name:24s} rms {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        out[key] = dry + signal.fftconvolve(bus, me.IRS["hall"]())[:n]
    return out[False], out[True]


def clean_tmp():
    """music_kit's renderer leaves one temp dir per stem: keep them in our run dir and empty it after each cue."""
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith(TMP_PREFIX):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def lufs_of(x):
    tmp = tempfile.mkdtemp() + "/m.wav"; wavfile.write(tmp, SR, np.asarray(x, np.float32)); return me.measure(tmp)


MUSIC = {"call": cue_call, "runaway": cue_runaway, "storm": cue_storm, "deep": cue_deep, "prayer": cue_prayer,
         "shore": cue_shore, "nineveh": cue_nineveh, "repent": cue_repent, "sulk": cue_sulk, "plant": cue_plant,
         "mercy": cue_mercy}
METER = {}
KEYS = {"call": "F major -> D minor", "runaway": "D minor -> F major -> D minor", "storm": "D minor", "deep": "F / D minor",
        "prayer": "F major", "shore": "F major", "nineveh": "D hijaz", "repent": "D minor -> F major",
        "sulk": "D minor", "plant": "F major -> D minor", "mercy": "F major"}
CUE_NOTES = {
    "call": "CALL theme (cello, then horn + cello + choir at the chime, harp run); Jonah's 'No way' interrupts with the JONAH theme (bassoon + tuba, D minor). Plays again at S08: same file, its first ~11 s (figure + pad).",
    "runaway": "Comic tiptoe: staccato pizz + wood blocks, bassoon creeps the JONAH theme staccato, xylophone up the gangplank, clarinet peek; sea sway (harp, flute) from the captain; bassoon snore at zzz; timpani flutter into the storm.",
    "storm": "Fast D minor: cello / bass gallop, tremolo violins + string waves, horn and trombone punches, timpani + soft cymbal; thunder hits; S04 thins to pad + heartbeat + JONAH theme confessing; trumpet climb and timpani roll to one big chord on the splash, then a hush.",
    "deep": "Underwater: very low pad, choir 'oo', a single falling harp note every 2 beats, far glock, cello whale calls (pitch-bent); bassoon sinks at the gulp.",
    "prayer": "Hushed: CALL theme far away on a muted horn + choir, the solo cello answers; at prayer_glow the cello sings the whole theme over strings + choir; harp + celesta.",
    "shore": "Dawn pad + harp and a soft timpani roll; at the pfft a trombone slide, whoop and xylophone tumble; then the bright beach tune on flute over plucked nylon strings, pizz bass, glock, shaker.",
    "nineveh": "Broad march in D hijaz: frame drums + bongos, tambourine, D drone (bass + tuba), shanai + oboe tune, qanun tremolos, horn calls.",
    "repent": "Hushed D minor (strings, choir oo, sorrowful cello) swelling; turns to F major when God sees it; flute lift, horn call figure + celesta at the forgiving chime; settles on F.",
    "sulk": "JONAH theme at its grumpiest: bassoon over plodding tuba + pizz + wood blocks, sour (flat) clarinet counter-line, a clarinet 'pffft' slide at the steam.",
    "plant": "Harp grows up the scale, xylophone + flute hop, worm clarinet wiggle, tuba munch, trombone 'wah-wah-wah-waaah' droop, shimmering strings in the sun, limp bassoon JONAH tune, last wah-wah; open on C.",
    "mercy": "CALL theme in full under God's voice (horn + cello, strings, choir, harp); at the heart glow the gentle JONAH theme (F major, bassoon + clarinet) joins it in the horns; held F chord, harp roll, celesta.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG


def drips(n, count, t0, t1, level, lo=1500, hi=7000, tau=.004):
    """Random tiny water ticks between t0 and t1 seconds."""
    y = np.zeros(n)
    for _ in range(count):
        m = int(.04 * SR); fc = R().uniform(lo, hi)
        d = me.bp(noise(m), fc * .7, min(fc * 1.5, 12000)) * me.env_exp(m, tau * R().uniform(.6, 1.8))
        me.place(y, d * R().uniform(.3, 1.0) * level, R().uniform(t0, t1))
    return y


def bubble(f0, secs=.12, rise=.5, amp=1.0):
    """One bubble: a sine that climbs in pitch while it decays (Minnaert 'bloop')."""
    m = int(secs * SR); t = np.arange(m) / SR
    f = f0 * (1 + rise * np.minimum(1, t / (secs * .6)))
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (secs * .35)) * np.minimum(1, t / .002)


# ----------------------------------------------------------------------------------------------- soft_chime
def sfx_soft_chime(ctx):
    """Golden light: four soft warm chime notes rising C6-F6-G6-Bb6 (the call figure), felt strikes, a little air."""
    secs = 3.4; n = int(secs * SR); y = np.zeros(n)
    for i, p_ in enumerate(("C6", "F6", "G6", "Bb6")):
        f = 440 * 2 ** ((note(p_) - 69) / 12)
        b = bell(2.9, f, [1, 2.0, 2.76, 4.1], [1, .25, .18, .06], [1.3, .7, .5, .25])
        place_(y, b * (.8 + .06 * i), .02 + i * .21 + R().normal(0, .005))
    y += me.hp(noise(n), 5000) * np.exp(-((np.arange(n) / SR - .5) / .45) ** 2) * .03
    return me.fit(me.room(y, "hall", .4), secs, fade_out=.9)


place_ = lambda dst, src, at: me.place(dst, src, at)


# ----------------------------------------------------------------------------------------------- seagulls
def gull_call(dur, f_hi, amp=1.0, bright=1.0):
    """One gull 'kee-ah': a short rising squeal that breaks into a longer falling cry, rough with a ~35 Hz flutter."""
    m = int(dur * SR); u = np.linspace(0, 1, m)
    f = np.interp(u, [0, .22, .30, 1], [f_hi * .72, f_hi, f_hi * .93, f_hi * .55])
    f = f * (1 + .02 * np.sin(2 * np.pi * 6 * u * dur))
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + .5 * np.sin(2 * ph) + .3 * np.sin(3 * ph) * bright
    y *= 1 + .35 * np.sin(2 * np.pi * 38 * np.arange(m) / SR) * np.clip(u * 3 - .6, 0, 1)
    env = np.minimum(1, u / .05) * np.where(u < .22, 1, np.exp(-(u - .22) * 2.4)) * np.minimum(1, (1 - u) / .15)
    return amp * y * env


def sfx_seagulls(ctx):
    """Four gulls over a soft surf: 'kee-ah' calls at different pitches and distances, a laughing triple cry."""
    secs = 4.6; n = int(secs * SR); y = np.zeros(n)
    for at, dur, f, a, br in ((.15, .75, 2300, 1.0, 1.0), (1.3, .6, 2650, .55, .7), (1.9, .85, 2050, .9, 1.0),
                              (3.0, .5, 2500, .5, .7)):
        g = gull_call(dur, f * R().uniform(.97, 1.03), a, br); place_(y, me.bp(g, 700, 6000), at)
    for k in range(3): place_(y, me.bp(gull_call(.22, 2200 - 80 * k), 800, 5500) * .7, 3.5 + k * .27)
    t = np.arange(n) / SR
    surf = me.lp(noise(n), 900) * (.5 + .5 * np.sin(2 * np.pi * t / 6.5 - 1)) ** 2 * .35
    y = y / (np.max(np.abs(y)) + 1e-9) + surf / (np.max(np.abs(surf)) + 1e-9) * .22
    return me.fit(me.room(y, "room", .15), secs, fade_in=.05, fade_out=.6)


# ----------------------------------------------------------------------------------------------- thunder
def sfx_thunder(ctx):
    """A big, round rumble (not scary): a soft-edged crack, then a rolling low boom that fades like a barrel on boards."""
    secs = 5.0; n = int(secs * SR); t = np.arange(n) / SR; nz = noise(n)
    crack = me.bp(nz, 600, 3500) * me.env_exp(n, .09) * np.minimum(1, t / .01) * .45
    roll = me.lp(noise(n), 140) * (1 + .6 * me.smooth_rand(n, 4)) * np.minimum(1, t / .06) * np.exp(-t / 1.5)
    mid = me.lp(noise(n), 420) * (1 + .5 * me.smooth_rand(n, 7)) * np.minimum(1, t / .05) * np.exp(-t / .75) * .6
    sub = np.sin(2 * np.pi * (52 - 14 * np.minimum(t, 2) / 2) * t) * np.minimum(1, t / .08) * np.exp(-t / 1.2) * .35
    y = crack + roll * 2.2 + mid + sub
    return me.fit(me.room(y, "hall", .3), secs, fade_out=1.0)


# ----------------------------------------------------------------------------------------------- rain
LOOP_SECS = {"rain_loop": 10.0}                      # whole-file seamless loop; rain_stop ends it
WRAP = 0.6


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def rain_bed(secs, gust=1.0):
    n = int(secs * SR); t = np.arange(n) / SR
    hiss = me.hp(me.lp(noise(n), 9500), 900) * .5
    wash = me.bp(noise(n), 250, 1100) * .35
    patter = drips(n, int(secs * 120), 0, secs - .05, 1.0, 1800, 8000, .003)
    drops = drips(n, int(secs * 14), 0, secs - .05, 1.3, 500, 2200, .012)
    mod = 1 + .06 * gust * me.smooth_rand(n, .5)
    return (hiss + wash) * mod + patter * .5 + drops * .35


def sfx_rain_loop(ctx):
    """10 s seamless rain: hiss, low wash, a patter of tiny drops and bigger plinks, slow gusts; wrap-folded loop."""
    return make_loop(rain_bed(LOOP_SECS["rain_loop"] + WRAP), LOOP_SECS["rain_loop"])


def sfx_rain_stop(ctx):
    """The rain ends: the patter thins, the hiss closes down to nothing in ~2 s, then a last few drips and a sigh of air."""
    secs = 4.2; n = int(secs * SR); t = np.arange(n) / SR
    y = rain_bed(secs) * np.exp(-t / .9) * np.clip(1.4 - t / 1.9, 0, 1)
    y += me.lp(noise(n), 700) * np.exp(-((t - 1.2) / .8) ** 2) * .1
    for i, at in enumerate((1.9, 2.5, 3.0, 3.7)):
        b = bubble(1500 + 200 * i, .07, .35, .5 - .08 * i); place_(y, b, at)
    return me.fit(me.room(y, "room", .2), secs, fade_in=.01, fade_out=.5)


# ----------------------------------------------------------------------------------------------- splash_big
def sfx_splash_big(ctx):
    """Jonah goes in: a deep 'THOOM', a wall of water noise that falls from bright to dull, foam fizz, a gulp of bubbles
    and slow slosh."""
    secs = 3.4; n = int(secs * SR); t = np.arange(n) / SR; nz = noise(n)
    thump = np.sin(2 * np.pi * (46 + 60 * np.exp(-t / .07)) * t) * np.exp(-t / .22) * 1.1
    wall = me.bp(nz, 150, 1200) * np.exp(-t / .45) * 1.3 + me.hp(noise(n), 1800) * np.exp(-t / .22) * .6
    fizz = me.hp(noise(n), 4500) * np.exp(-t / .9) * (1 + .5 * me.smooth_rand(n, 30)) * .25
    slosh = me.lp(noise(n), 450) * (.5 + .5 * np.sin(2 * np.pi * t * 1.3 - .5)) * np.exp(-t / 1.3) * .5 * np.minimum(1, t / .3)
    y = thump + wall + fizz + slosh
    for k in range(16):
        at = .1 + R().exponential(.7) + k * .05; place_(y, bubble(R().uniform(250, 1200), R().uniform(.06, .2), .5, R().uniform(.1, .35)), at)
    return me.fit(me.room(y, "hall", .3), secs, fade_in=.004, fade_out=.9)


# ----------------------------------------------------------------------------------------------- bubbles
def sfx_bubbles(ctx):
    """Underwater: a rumbling lowpass bed and a stream of bubbles, big slow gloops first, then a thinning froth of tiny
    ones."""
    secs = 5.0; n = int(secs * SR); t = np.arange(n) / SR
    y = me.lp(noise(n), 260) * .25 * (1 + .4 * me.smooth_rand(n, 1.5)) * np.minimum(1, t / .5) * np.clip(1.2 - t / secs, 0, 1)
    for k in range(34):
        at = R().exponential(1.5) if k > 5 else R().uniform(0, 1.0)
        if at > secs - .5: continue
        big = at < 1.6
        f0 = R().uniform(180, 520) if big else R().uniform(700, 2800)
        place_(y, bubble(f0, R().uniform(.09, .26) if big else R().uniform(.03, .09), R().uniform(.3, .7), R().uniform(.25, 1.0) * (1.0 if big else .55)), at)
    y = me.lp(y, 6500)
    return me.fit(me.room(y, "room", .3), secs, fade_in=.05, fade_out=1.0)


# ----------------------------------------------------------------------------------------------- creature sounds
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


def sfx_gulp(ctx):
    """Short and comic: a wet throat 'GLUP' (voiced 'u->o' sliding down) with two bubble blips, a squelch, a tiny 'glk'."""
    secs = .85; n = int(secs * SR)
    v = creature(.42, [(0, 250), (.12, 190), (.42, 95)], [(0, "u"), (.5, "o"), (1, "u")], .85, rough=.55, rough_hz=42, breath=.25,
                 amp_pts=[(0, 0), (.03, 1), (.3, .9), (.42, 0)])
    y = np.zeros(n); place_(y, v / (np.std(v) + 1e-9) * .45, .04)
    place_(y, bubble(520, .1, .6, .5), .02); place_(y, bubble(330, .14, .7, .55), .22)
    sq = me.bp(noise(n), 600, 2600) * me.env_exp(n, .03, .13) * .5; y += sq
    place_(y, creature(.14, [(0, 150), (.14, 100)], [(0, "u"), (1, "o")], .85, rough=.4, amp_pts=[(0, 0), (.02, 1), (.14, 0)]) * .18, .55)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.1)


def sfx_burp(ctx):
    """A big, silly belch: a rough low 'BWAAARP' (95-130-70 Hz with a sub-octave), cheeky wobble, a bubble-pop tail."""
    secs = 1.15; n = int(secs * SR)
    v = creature(.8, [(0, 100), (.08, 140), (.4, 112), (.8, 66)], [(0, "u"), (.12, "ah"), (.5, "o"), (1, "u")], .8, rough=.95,
                 rough_hz=58, breath=.28, sub=.6, amp_pts=[(0, 0), (.04, 1), (.5, .9), (.8, 0)])
    y = np.zeros(n); place_(y, v / (np.std(v) + 1e-9) * .5, .03)
    place_(y, bubble(900, .05, .8, .4), .88); place_(y, bubble(1300, .04, .8, .3), .96)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.12)


def sfx_spit_pop(ctx):
    """'Pfffft-POP!': a wet raspberry (noise amplitude-modulated at ~38 Hz, falling), then a cork pop (sine drop) and
    a small splat."""
    secs = 1.15; n = int(secs * SR); t = np.arange(n) / SR
    rasp = me.bp(noise(n), 700, 3800) * (.55 + .45 * np.sin(2 * np.pi * 38 * t * (1 - .25 * t))) * np.minimum(1, t / .02) * np.clip(1 - t / .5, 0, 1) ** 1.2
    y = rasp * .8
    m = int(.12 * SR); tt = np.arange(m) / SR
    pop = np.sin(2 * np.pi * np.cumsum(1200 * np.exp(-tt / .018) + 250) / SR) * np.exp(-tt / .03) * 1.4
    place_(y, pop, .52); place_(y, me.bp(noise(m), 1200, 5000) * me.env_exp(m, .012) * .6, .52)
    sp = int(.25 * SR); place_(y, me.lp(noise(sp), 1800) * me.env_exp(sp, .05) * .6 * np.minimum(1, np.arange(sp) / SR / .005), .7)
    place_(y, bubble(700, .08, .5, .3), .85)
    return me.fit(me.room(y, "room", .1), secs, fade_out=.15)


# ----------------------------------------------------------------------------------------------- grow_whoosh
def sfx_grow_whoosh(ctx):
    """The little plant shoots up: a rising airy sweep (band-pass rushing 300 -> 4000 Hz), a glassy pentatonic climb, leaf
    rustle, and a springy 'boing' at the top."""
    secs = 2.2; n = int(secs * SR); t = np.arange(n) / SR
    sweep = me.wah_filter(noise(n), 300 * (4000 / 300) ** np.clip(t / 1.4, 0, 1), .6, 1.5)
    sweep *= np.sin(np.pi * np.clip(t / 1.6, 0, 1)) ** 1.6
    y = sweep * 1.5
    for i, p_ in enumerate(["F5", "G5", "A5", "C6", "D6", "F6", "G6", "A6"]):
        f = 440 * 2 ** ((note(p_) - 69) / 12); place_(y, bell(.5, f, [1, 2.0, 3.0], [1, .2, .06], [.12, .06, .03]) * .45, .08 + i * .15)
    place_(y, me.hp(noise(n), 3500) * (me.smooth_rand(n, 30) ** 2) * .12 * np.sin(np.pi * np.clip(t / 1.6, 0, 1)), 0)
    m = int(.5 * SR); tt = np.arange(m) / SR
    f = 330 + 90 * np.sin(2 * np.pi * 9 * tt) * np.exp(-tt / .3) + 200 * np.exp(-tt / .1)
    place_(y, tone(f, .5, .3) * np.exp(-tt / .18) * np.minimum(1, tt / .004), 1.55)
    return me.fit(me.room(y, "room", .2), secs, fade_out=.35)


# ----------------------------------------------------------------------------------------------- munch
def sfx_munch(ctx):
    """The worm munches: four crunchy 'nom' bites (a burst of tiny crackles + a wet smack + a short round 'o'), the last
    one slower, then a happy 'mm'."""
    secs = 2.3; n = int(secs * SR); y = np.zeros(n)
    for i, at in enumerate((.05, .5, .95, 1.5)):
        crunch = np.zeros(int(.12 * SR))
        for _ in range(R().integers(7, 12)):
            m = int(.012 * SR); c = me.bp(noise(m), 900, 4500) * me.env_exp(m, .003)
            me.place(crunch, c * R().uniform(.4, 1.0), R().uniform(0, .09))
        place_(y, crunch * 1.4, at)
        m = int(.06 * SR); place_(y, me.bp(noise(m), 1500, 5500) * me.env_exp(m, .008) * .6, at + .06)
        nom = creature(.17, [(0, 210 - 18 * i), (.17, 150 - 10 * i)], [(0, "u"), (.4, "o"), (1, "u")], 1.05, rough=.2, breath=.12,
                       amp_pts=[(0, 0), (.02, 1), (.12, .7), (.17, 0)])
        place_(y, nom / (np.std(nom) + 1e-9) * .22, at + .02)
    mm = creature(.55, [(0, 190), (.25, 215), (.55, 180)], [(0, "u"), (1, "u")], 1.05, rough=.1, breath=.05, amp_pts=[(0, 0), (.1, 1), (.4, .8), (.55, 0)])
    place_(y, mm / (np.std(mm) + 1e-9) * .2, 1.85)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.2)


# ----------------------------------------------------------------------------------------------- cicadas_heat
def sfx_cicadas_heat(ctx):
    """Burning noon: five cicadas buzzing in pulsing 'rrrr' bursts (a 5-6 kHz carrier chopped at 70-110 Hz), a hot,
    shimmering air bed; fades in over 1.5 s and out over 2.5 s."""
    secs = 9.5; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for k in range(5):
        fc = R().uniform(4300, 6200); rate = R().uniform(70, 105); on = R().uniform(.8, 1.6); off = R().uniform(.25, .7)
        at = R().uniform(0, .8)
        while at < secs - .3:
            d = min(on * R().uniform(.8, 1.2), secs - at); m = int(d * SR); tt = np.arange(m) / SR
            car = np.sin(2 * np.pi * fc * (1 + .004 * np.sin(2 * np.pi * 3 * tt)) * tt) + .4 * np.sin(2 * np.pi * fc * 2 * tt)
            chop = (.5 + .5 * np.sign(np.sin(2 * np.pi * rate * tt))) * .7 + .3
            env = np.minimum(1, tt / .12) * np.minimum(1, (d - tt) / .2)
            place_(y, car * chop * env * R().uniform(.5, 1.0), at); at += d + off * R().uniform(.7, 1.4)
    y = me.bp(y, 3000, 8500)
    air = me.bp(noise(n), 2500, 7000) * (1 + .5 * me.smooth_rand(n, 1)) * .06
    y = y / (np.max(np.abs(y)) + 1e-9) + air
    y *= np.minimum(1, t / 1.5) * np.minimum(1, (secs - t) / 2.5) ** 1.5
    return me.fit(me.room(y, "room", .15), secs, fade_out=.05)


SFX = {"soft_chime": sfx_soft_chime, "seagulls": sfx_seagulls, "thunder": sfx_thunder, "rain_loop": sfx_rain_loop,
       "rain_stop": sfx_rain_stop, "splash_big": sfx_splash_big, "bubbles": sfx_bubbles, "gulp": sfx_gulp, "burp": sfx_burp,
       "spit_pop": sfx_spit_pop, "grow_whoosh": sfx_grow_whoosh, "munch": sfx_munch, "cicadas_heat": sfx_cicadas_heat}
SFX_SEED = {}
# SFX are not ducked by the engine (they play on top of speech at gainDb), so 2026-11-15: gains 2-4 dB lower, long tails
# shaped away (SFX_SHAPE = seconds kept, then decay time constant); the punchy front stays at the same peak.
SFX_GAIN = {"soft_chime": -13, "seagulls": -15, "thunder": -9, "rain_loop": -20, "rain_stop": -17, "splash_big": -8,
            "bubbles": -13, "gulp": -9, "burp": -9, "spit_pop": -9.5, "grow_whoosh": -12, "munch": -11, "cicadas_heat": -19}
SFX_SHAPE = {"soft_chime": (0.9, 0.6), "seagulls": (1.6, 1.2), "thunder": (0.4, 0.9), "splash_big": (0.5, 0.8),
             "bubbles": (1.2, 1.5), "grow_whoosh": (1.2, 0.5)}
SFX_NOTES = {"soft_chime": "four warm chime notes C6-F6-G6-Bb6 (the call figure), felt strikes, hall",
             "seagulls": "4 'kee-ah' gull cries (rising squeal, falling cry, 38 Hz flutter) + a laughing triple cry over soft surf",
             "thunder": "soft-edged crack, rolling 140 Hz boom, 52 Hz sub, 5 s decay in a hall; round, not scary",
             "rain_loop": "seamless 10 s loop (wrap-folded): hiss, low wash, ~1200 tiny drops, plinks, slow gusts; `rain_stop` ends it",
             "rain_stop": "rain thinning and closing down over ~2 s, then four last drips",
             "splash_big": "deep 'THOOM' (46-106 Hz drop), falling water wall, foam fizz, slosh, 16 bubbles, hall",
             "bubbles": "low rumble bed + big slow gloops first, then a thinning froth of tiny bubbles (34 in all)",
             "gulp": "comic wet 'GLUP' (voiced u>o, 250 to 95 Hz) with two bubbles, a squelch and a small 'glk'; 0.85 s",
             "burp": "silly 'BWAAARP' (rough formant voice 100-140-66 Hz + sub-octave) and a two-bubble pop; 1.15 s",
             "spit_pop": "wet raspberry (38 Hz AM noise) falling into a cork 'POP', a splat and one bubble",
             "grow_whoosh": "rising airy sweep 300 to 4000 Hz, glassy F-pentatonic climb, leaf rustle, springy 'boing'",
             "munch": "four crunchy 'nom' bites (crackle bursts + wet smack + short voiced 'o') and a happy 'mm'",
             "cicadas_heat": "5 cicadas, 5-6 kHz carriers chopped at 70-105 Hz in 'rrrr' bursts, hot air bed, 1.5 s in / 2.5 s out; one-shot"}




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
    me.seed("jonah/" + name); ctx = Ctx(tl, name, c["t"], c["span"], c["secs"], c["last"])
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
                        "tools/story/music_jonah.py after the timeline is re-timed so the in-cue hits follow.",
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
        me.seed(SFX_SEED.get(sid, "jonah/" + sid))
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
    mix = vm.engine_mix("jonah", tl, "zh", MUSIC_DIR, SFX_DIR); rows = vm.table(tl, mix)
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
BASELINE = {"jn_01": 15.5, "jn_02": 10.0, "jn_03": 8.6, "jn_04": 10.7, "jn_05": 10.4, "jn_06": 11.1, "jn_07": 9.1, "jn_08": 11.5, "jn_09": 13.2, "jn_10": 15.0, "jn_11": 11.3, "jn_12": 10.4, "jn_13": 11.9, "jn_14": 16.4, "jn_15": 16.1, "jn_16": 10.8, "jn_17": 16.1, "jn_18": 13.5, "jn_19": 12.6, "jn_20": 13.8, "jn_21": 12.8, "jn_22": 13.9, "jn_23": 10.2, "jn_24": 11.0, "jn_25": 9.5, "jn_26": 13.4, "jn_27": 17.1, "jn_28": 13.5, "jn_29": 11.7}


def hit_rows(tl):
    """Where every SFX / glow lands inside its cue in the Chinese play and in the English play (same cue file, so the
    English offset is how far its hit drifts from the composed moment)."""
    en = vm.lang_timeline("jonah", "en"); rows = []
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
    ap.add_argument("--tmp", default="/tmp/jonah_music", help="scratch dir (emptied per cue, removed at exit)")
    ap.add_argument("--spec", default="", help="also write spectrogram PNGs of every output into this dir")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    os.makedirs(a.tmp, exist_ok=True)
    tempfile.tempdir = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=a.tmp)
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    os.makedirs(MUSIC_DIR, exist_ok=True); os.makedirs(SFX_DIR, exist_ok=True)
    tl = vm.lang_timeline("jonah", "zh")      # the play as the phone runs it in Chinese (re-timed to the zh clips)
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
    if a.spec: spectrograms(a.spec)
