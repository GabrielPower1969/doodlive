#!/usr/bin/env python3
"""Score and sound effects for David & Goliath (docs/david-goliath/CONTRACT.md section 7, MUSIC.md).

Music is composed as MIDI (mido) and rendered with FluidSynth + macOS's General MIDI bank
(gs_instruments.dls, ships with CoreAudio), the same way tools/make_music.py does for the angel.
Sound effects that General MIDI has no good patch for are synthesised here with numpy/scipy.

Every name comes from assets/david-goliath/timeline.json: each `music.cue` and `sfx.id` there must exist
after a run (the script asserts it). Music cue lengths follow the cue spans in the timeline plus a 0.6 s
crossfade tail (STORYBOARD: "a new cue crossfades out the previous one (0.6 s)").

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/david-goliath/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated
  assets/david-goliath/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/david-goliath/audio/music/cues.json        cue lengths, loudness, crossfade rule
  assets/david-goliath/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/david-goliath/audio/preview_mix.mp3        rough full-length mix placed at timeline times
                                                    (voice clips are included when they exist)

Usage: python3 tools/make_dg_music.py [--skip-music] [--skip-sfx] [--skip-preview]
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg
"""
import argparse, json, os, re, subprocess, sys, tempfile, warnings
import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DG = f"{ROOT}/assets/david-goliath"
TIMELINE = f"{DG}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{DG}/audio/music", f"{DG}/audio/sfx", f"{DG}/audio/voice"
PREVIEW = f"{DG}/audio/preview_mix.mp3"
DLS = "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls"
SR = 44100
XFADE = 0.6            # seconds, from STORYBOARD conventions
MUSIC_LUFS = -20.0     # CONTRACT section 7
SFX_PEAK_DB = -3.0     # CONTRACT section 7
warnings.filterwarnings("ignore", category=wavfile.WavFileWarning)  # FluidSynth writes a LIST chunk
RNG = np.random.default_rng(1617)  # 1 Samuel 16-17; fixed seed so reruns are byte-stable

# ----------------------------------------------------------------------------------------------- MIDI helpers
TPB = 480
N = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)
def note(name):  # "F4" -> 65, "Bb2" -> 46, "C#3" -> 49
    return 12 * (int(name[-1]) + 1) + N[name[0]] + (1 if "#" in name else -1 if "b" in name[1:] else 0)

class Track:
    def __init__(self, mid, ch, program, name, vol=100, pan=64, reverb=60):
        self.t = MidiTrack(); mid.tracks.append(self.t); self.ch = ch; self.events = []
        self.t.append(MetaMessage("track_name", name=name, time=0))
        if ch != 9: self.t.append(Message("program_change", channel=ch, program=program, time=0))
        for cc, v in ((7, vol), (10, pan), (91, reverb)):
            self.t.append(Message("control_change", channel=ch, control=cc, value=v, time=0))
    def add(self, beat, pitch, dur, vel=90):
        if isinstance(pitch, str): pitch = note(pitch)
        on, off = int(round(beat * TPB)), int(round((beat + dur) * TPB))
        self.events.append((on, 1, pitch, max(1, min(127, int(vel))))); self.events.append((off, 0, pitch, 0))
    def chord(self, beat, pitches, dur, vel=80, spread=0):
        for k, p in enumerate(pitches): self.add(beat, p, dur, vel - k * spread)
    def finish(self):
        last = 0
        for tick, kind, pitch, vel in sorted(self.events, key=lambda e: (e[0], e[1])):
            self.t.append(Message("note_on" if kind else "note_off", channel=self.ch, note=pitch,
                                  velocity=vel, time=tick - last)); last = tick
        self.t.append(MetaMessage("end_of_track", time=0))

def new_mid(bpm):
    mid = MidiFile(ticks_per_beat=TPB); meta = MidiTrack(); mid.tracks.append(meta)
    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(bpm), time=0)); meta.append(MetaMessage("end_of_track", time=0))
    return mid

def finish_all(*tracks):
    for t in tracks: t.finish()

# GM programs (0-based) and GM drum keys used below
STRINGS, SLOW_STR, TREM_STR, PIZZ, HARP, CELLO, CBASS = 48, 49, 44, 45, 46, 42, 43
CHOIR, TRUMPET, TROMBONE, TUBA, HORN, BRASS = 52, 56, 57, 58, 60, 61
FLUTE, RECORDER, PANFLUTE, OBOE, BASSOON, CLARINET = 73, 74, 75, 68, 70, 71
CELESTA, GLOCK, XYLO, TIMPANI, TAIKO, ORCH_HIT = 8, 9, 13, 47, 116, 55
KICK, SNARE, CRASH, RIDE, TRIANGLE, TAMB = 36, 38, 49, 51, 81, 54

# ----------------------------------------------------------------------------------------------- music cues
def theme_tension(secs):
    """Goliath: D minor, 80 bpm, heavy low strings, tuba stomp motif, timpani/taiko. S01-S03 (0-26.4 s)."""
    bpm = 80; mid = new_mid(bpm); beats = secs * bpm / 60  # 36 beats = 9 bars
    cb = Track(mid, 0, CBASS, "contrabass", 100, 50, 40); vc = Track(mid, 1, CELLO, "cello", 92, 56, 45)
    tuba = Track(mid, 2, TUBA, "tuba", 104, 70, 40); tbn = Track(mid, 3, TROMBONE, "trombone", 84, 76, 50)
    timp = Track(mid, 4, TIMPANI, "timpani", 104, 64, 50); taiko = Track(mid, 5, TAIKO, "taiko", 96, 60, 40)
    pad = Track(mid, 6, STRINGS, "strings", 72, 70, 80); trem = Track(mid, 7, TREM_STR, "tremolo", 62, 84, 80)
    bsn = Track(mid, 8, BASSOON, "bassoon", 84, 44, 50)
    # 9 bars: Dm Dm Bb A | Dm Dm Bb A | Dm (fading, hand over to the shepherd at 26.4 s = beat 35.2)
    roots = ["D2", "D2", "Bb1", "A1", "D2", "D2", "Bb1", "A1", "D2"]
    pads = [["D3", "A3", "F4"], ["D3", "A3", "F4"], ["Bb2", "F3", "D4"], ["A2", "E3", "C#4"]] * 2 + [["D3", "A3", "F4"]]
    for bar, r in enumerate(roots):
        b = bar * 4; rp = note(r); last = bar == 8
        for q in range(4):                                     # heavy quarter-note "stomp" in the basses
            v = (96 if q in (0, 2) else 70) - (30 if last else 0)
            cb.add(b + q, rp, 0.85, v); vc.add(b + q, rp + 12, 0.85, v - 14)
        timp.add(b, rp + 12 if rp + 12 <= note("F3") else rp, 1.0, 100 - (35 if last else 0))
        if not last: timp.add(b + 2, rp + 7 if rp + 7 <= note("F3") else rp - 5, 0.8, 78)
        if bar % 2 == 0 and not last: taiko.add(b, 60, 1.5, 92)
        if bar >= 2: pad.chord(b, [note(p) for p in pads[bar]], 4, 52 - (14 if last else 0), 4)
    # Goliath's stomping motif, tuba + trombone, bars 1-2 and 5-6 (like Peter and the Wolf: big, not scary)
    motif = [(0, "D2", 1), (1, "D2", 1), (2, "F2", 0.75), (2.75, "E2", 0.25), (3, "D2", 1), (4, "A1", 1.5), (5.5, "C#2", 0.5), (6, "D2", 2)]
    for start in (0, 16):
        for b, p, d in motif:
            tuba.add(start + b, p, d * 0.95, 104); tbn.add(start + b, note(p) + 12, d * 0.95, 78)
    # bars 7-8 (S03, the armies are afraid): shimmering high tremolo and a cheeky bassoon laugh figure
    for b, ps in ((24, ["A4", "Bb4"]), (26, ["A4", "Bb4"]), (28, ["G4", "Bb4"]), (30, ["E4", "A4"])):
        trem.chord(b, [note(p) for p in ps], 2, 56, 4)
    for b, p, d in [(25, "D3", 0.5), (25.5, "F3", 0.5), (26, "A3", 0.5), (26.5, "F3", 0.5), (27, "D3", 1),
                    (29, "A2", 0.5), (29.5, "C#3", 0.5), (30, "E3", 0.5), (30.5, "C#3", 0.5), (31, "A2", 1)]:
        bsn.add(b, p, d * 0.9, 80)
    finish_all(cb, vc, tuba, tbn, timp, taiko, pad, trem, bsn)
    return mid

def theme_shepherd(secs):
    """David: G major, 3/4 at 90 bpm, pan-flute (shepherd's pipe) melody over harp and pizzicato. S04-S06."""
    bpm = 90; mid = new_mid(bpm)                     # bar = 2.0 s, 16 bars = 32 s
    pipe = Track(mid, 0, PANFLUTE, "pan flute", 96, 58, 70); harp = Track(mid, 1, HARP, "harp", 92, 74, 70)
    pizz = Track(mid, 2, PIZZ, "pizzicato", 80, 52, 50); pad = Track(mid, 3, SLOW_STR, "slow strings", 64, 64, 85)
    horn = Track(mid, 4, HORN, "horn", 70, 60, 70); glock = Track(mid, 5, CELESTA, "celesta", 66, 86, 80)
    chords = {"G": ["G2", "D3", "G3", "B3"], "C": ["C3", "G3", "C4", "E4"], "Em": ["E2", "B2", "E3", "G3"], "D": ["D3", "A3", "D4", "F#4"]}
    prog = ["G", "G", "C", "G", "Em", "C", "D", "D", "G", "G", "C", "G", "Em", "C", "D", "G"]
    for bar, c in enumerate(prog):
        b = bar * 3; ps = [note(p) for p in chords[c]]
        pizz.add(b, ps[0], 0.5, 84); pizz.add(b + 2, ps[1], 0.5, 64)
        for k, p in enumerate([ps[1], ps[2], ps[3] + 0, ps[2] + 12 if ps[2] + 12 < 84 else ps[2], ps[3], ps[2]]):
            harp.add(b + k * 0.5, p + 12, 0.7, 70 + (10 if k == 0 else 0))
        pad.chord(b, ps[1:] if bar < 15 else ps, 3, 44, 3)
        if 5 <= bar <= 10:                                   # S05: lion, bear and Saul's armour; a brave horn line
            horn.add(b, ps[2], 2.8, 58)
    mel = [  # (bar, beat-in-bar, note, beats)
        (0, 0, "D5", 2), (0, 2, "B4", 1), (1, 0, "G4", 2), (1, 2, "A4", 1), (2, 0, "C5", 1), (2, 1, "E5", 1), (2, 2, "D5", 1),
        (3, 0, "B4", 3), (4, 0, "B4", 2), (4, 2, "G4", 1), (5, 0, "E4", 2), (5, 2, "G4", 1), (6, 0, "A4", 1), (6, 1, "B4", 1),
        (6, 2, "C5", 1), (7, 0, "A4", 3),
        (8, 0, "D5", 2), (8, 2, "B4", 1), (9, 0, "G4", 2), (9, 2, "A4", 1), (10, 0, "C5", 1), (10, 1, "E5", 1), (10, 2, "D5", 1),
        (11, 0, "B4", 2), (11, 2, "D5", 1), (12, 0, "E5", 2), (12, 2, "D5", 1), (13, 0, "C5", 2), (13, 2, "B4", 1),
        (14, 0, "A4", 1), (14, 1, "B4", 1), (14, 2, "A4", 1), (15, 0, "G4", 3.3)]
    for bar, bb, p, d in mel:
        pipe.add(bar * 3 + bb, p, d * 0.95, 78 if bar < 12 else 66)
    # S06 by the brook (bars 13-15): little celesta droplets
    for b in (39, 40.5, 42, 43.5, 45, 46.5):
        glock.add(b, note("D6") + int(RNG.integers(0, 3)) * 2, 0.5, 52)
    finish_all(pipe, harp, pizz, pad, horn, glock)
    return mid

def theme_faith(secs):
    """S07: Goliath sneers (uneasy D minor), then David's key line: brave rise C - F - G - C with horns and choir."""
    bpm = 72; mid = new_mid(bpm)                     # beat = 0.833 s; 10.4 s = 12.5 beats
    trem = Track(mid, 0, TREM_STR, "tremolo", 70, 64, 70); bsn = Track(mid, 1, BASSOON, "bassoon", 80, 44, 50)
    strs = Track(mid, 2, STRINGS, "strings", 92, 70, 80); horn = Track(mid, 3, HORN, "horns", 96, 56, 70)
    choir = Track(mid, 4, CHOIR, "choir", 82, 64, 90); bass = Track(mid, 5, CBASS, "contrabass", 86, 50, 50)
    timp = Track(mid, 6, TIMPANI, "timpani", 90, 64, 50); harp = Track(mid, 7, HARP, "harp", 80, 80, 70)
    trem.chord(0, [note("D3"), note("A3"), note("F4")], 4.6, 48, 3); bass.add(0, "D2", 4.6, 64)
    for b, p, d in [(0.5, "D3", 0.5), (1, "C#3", 0.5), (1.5, "D3", 0.5), (2, "F3", 1), (3, "E3", 0.5), (3.5, "D3", 0.5)]:
        bsn.add(b, p, d * 0.9, 74)                            # the sneer (dg_13, 58.8 s)
    harp.add(4.4, "C4", 1, 60)                                # glissando-ish turn toward brave (dg_14 starts 62.2 s = beat 5.0)
    for k, p in enumerate(["G3", "C4", "E4", "G4", "C5", "E5"]): harp.add(4.4 + k * 0.1, p, 1.2, 64 + k * 4)
    prog = [(5, ["C3", "G3", "C4", "E4"], "C2"), (7, ["A2", "F3", "C4", "F4"], "F2"), (9, ["B2", "G3", "D4", "G4"], "G2"), (11, ["C3", "G3", "C4", "E4"], "C2")]
    for i, (b, ps, r) in enumerate(prog):
        d = 2 if i < 3 else 1.6
        strs.chord(b, [note(p) for p in ps], d, 66 + i * 8, 3); bass.add(b, r, d, 76 + i * 6)
        choir.chord(b, [note(p) + 12 for p in ps[1:]], d, 50 + i * 8, 3)
    for b, p, d in [(5, "G4", 1), (6, "C5", 1), (7, "C5", 0.75), (7.75, "D5", 0.25), (8, "F5", 1),
                    (9, "E5", 0.75), (9.75, "D5", 0.25), (10, "D5", 1), (11, "E5", 1.6)]:
        horn.add(b, p, d * 0.95, 92)
    for k in range(12):                                       # timpani roll, crescendo into the battle cue
        timp.add(10.6 + k * 0.125, "G2", 0.12, 40 + k * 5)
    finish_all(trem, bsn, strs, horn, choir, bass, timp, harp)
    return mid

def theme_battle(secs):
    """S08: the run and the sling. 144 bpm, C minor ostinato, chromatic rising bass, snare roll; peaks at the release."""
    bpm = 144; mid = new_mid(bpm)                    # beat = 0.4167 s; 5.85 s = 14 beats; release 72.6 s = beat 11.5
    ost = Track(mid, 0, STRINGS, "strings ostinato", 100, 70, 50); low = Track(mid, 1, CBASS, "basses", 100, 54, 40)
    brass = Track(mid, 2, BRASS, "brass", 96, 60, 60); timp = Track(mid, 3, TIMPANI, "timpani", 100, 64, 40)
    drums = Track(mid, 9, 0, "drums", 96, 64, 40); hi = Track(mid, 4, TREM_STR, "high tremolo", 76, 84, 70)
    steps = [("C2", ["C4", "Eb4", "G4"]), ("D2", ["D4", "F4", "Ab4"]), ("Eb2", ["Eb4", "G4", "Bb4"]),
             ("F2", ["F4", "Ab4", "C5"]), ("G2", ["G4", "B4", "D5"]), ("Ab2", ["Ab4", "C5", "Eb5"])]
    for i, (r, ch) in enumerate(steps):                       # one step up every 2 beats
        b = i * 2; rp = note(r)
        for k in range(8):                                    # 8th-note ostinato
            ost.add(b + k * 0.25, rp + 12 + (7 if k % 4 == 2 else 0), 0.22, 70 + i * 6)
        low.add(b, rp, 1.9, 84 + i * 6)
        brass.chord(b, [note(p) for p in ch], 1.8, 64 + i * 8, 4)
        timp.add(b, rp + 12 if rp + 12 <= note("A3") else rp, 0.4, 80 + i * 6); timp.add(b + 1, rp + 12 if rp + 12 <= note("A3") else rp, 0.3, 66 + i * 6)
    # beat 12-14: hold the dominant (G) with tremolo strings at full stretch: the stone is in the air
    hi.chord(11.5, [note("G5"), note("B5"), note("D6")], 2.6, 96, 4); low.add(12, "G1", 2.2, 110)
    brass.chord(12, [note("G3"), note("B3"), note("D4"), note("G4")], 2.0, 108, 3)
    n = 0
    for k in range(int(11.5 / 0.125)):                        # snare roll 32nds, crescendo
        drums.add(k * 0.125, SNARE, 0.1, 30 + k * 0.85); n += 1
    drums.add(0, CRASH, 1.5, 70); drums.add(11.5, CRASH, 2.0, 112)
    finish_all(ost, low, brass, timp, drums, hi)
    return mid

def sting_hit(secs):
    """73.05 s one-shot: orchestra hit on the stone, dizzy xylophone wobble, a comic tumbling tuba slide (fall 74.0 s),
    a boom on the landing (75.2 s = 2.15 s into the cue), then silence until theme_victory (76.0 s)."""
    bpm = 120; mid = new_mid(bpm)                    # beat = 0.5 s
    hit = Track(mid, 0, ORCH_HIT, "orch hit", 112, 64, 50); timp = Track(mid, 1, TIMPANI, "timpani", 110, 64, 50)
    xylo = Track(mid, 2, XYLO, "xylophone", 84, 80, 60); tuba = Track(mid, 3, TUBA, "tuba", 100, 50, 40)
    drums = Track(mid, 9, 0, "drums", 100, 64, 60); bsn = Track(mid, 4, BASSOON, "bassoon", 80, 70, 50)
    hit.chord(0, [note("C4"), note("E4"), note("G4"), note("C5")], 0.6, 120)
    timp.add(0, "C3", 1.0, 120); drums.add(0, CRASH, 2.5, 110); drums.add(0, KICK, 0.5, 120)
    for k in range(10):                                       # dizzy wobble (dizzy_stars at 73.3 s)
        xylo.add(0.5 + k * 0.125, "E6" if k % 2 == 0 else "F6", 0.12, 72 - k * 3)
    slide = ["G2", "F#2", "F2", "E2", "Eb2", "D2", "C#2", "C2"]  # tumbling down from 74.0 s (beat 1.9)
    for k, p in enumerate(slide):
        tuba.add(1.9 + k * 0.28, p, 0.27, 96); bsn.add(1.9 + k * 0.28, note(p) + 12, 0.27, 70)
    timp.add(4.3, "C2" if note("C2") >= 40 else "F2", 1.2, 124); drums.add(4.3, KICK, 0.5, 124); drums.add(4.3, CRASH, 1.4, 90)
    finish_all(hit, timp, xylo, tuba, drums, bsn)
    return mid

def theme_victory(secs):
    """S10-S11: bright C major fanfare (cheer), lighter dance (victory jump), then a gentle choir 'Amen' under the
    prayer and the closing line (from 84.2 s = 8.2 s into the cue)."""
    bpm = 100; mid = new_mid(bpm)                    # beat = 0.6 s; 13.0 s = 21.7 beats
    tpt = Track(mid, 0, TRUMPET, "trumpets", 100, 58, 60); horn = Track(mid, 1, HORN, "horns", 88, 70, 70)
    strs = Track(mid, 2, STRINGS, "strings", 92, 64, 80); timp = Track(mid, 3, TIMPANI, "timpani", 96, 64, 50)
    glock = Track(mid, 4, GLOCK, "glockenspiel", 80, 84, 70); choir = Track(mid, 5, CHOIR, "choir", 92, 64, 95)
    harp = Track(mid, 6, HARP, "harp", 86, 76, 80); bass = Track(mid, 7, CBASS, "contrabass", 84, 50, 50)
    drums = Track(mid, 9, 0, "drums", 84, 64, 50)
    # 0-6 beats: fanfare
    for b, p, d in [(0, "G4", 0.5), (0.5, "C5", 0.5), (1, "E5", 0.5), (1.5, "G5", 1.5), (3, "E5", 0.5), (3.5, "G5", 0.5), (4, "C6", 2)]:
        tpt.add(b, p, d * 0.95, 110); horn.add(b, note(p) - 12, d * 0.95, 90)
    for b, ch, r in [(0, ["C4", "E4", "G4"], "C2"), (2, ["F4", "A4", "C5"], "F2"), (4, ["G4", "C5", "E5"], "C2")]:
        strs.chord(b, [note(p) for p in ch], 2, 84, 3); bass.add(b, r, 2, 92)
    for b in (0, 1.5, 4): timp.add(b, "C3" if b != 1.5 else "G2", 0.6, 112)
    drums.add(0, CRASH, 2, 96); drums.add(4, CRASH, 2, 90)
    # 6-13 beats: light, joyful (victory jump + chime at 80.0 s = beat 6.7)
    for b, ch, r in [(6, ["C4", "E4", "G4"], "C2"), (8, ["F4", "A4", "C5"], "F2"), (10, ["G4", "B4", "D5"], "G2"), (12, ["C4", "E4", "G4"], "C2")]:
        strs.chord(b, [note(p) for p in ch], 2, 64, 3); bass.add(b, r, 1.8, 70)
        for k, p in enumerate(ch + [ch[1]]): harp.add(b + k * 0.5, note(p) + 12, 0.6, 70)
    for b, p in [(6, "E6"), (6.5, "G6"), (7, "C7"), (8, "A6"), (8.5, "F6"), (9, "C7"), (10, "B6"), (10.5, "G6"), (11, "D7"), (12, "C7")]:
        glock.add(b, p, 0.5, 70)
    for b in (6, 7, 8, 9, 10, 11): drums.add(b + 0.5, TAMB, 0.2, 50)
    # 13.7-21.7 beats: prayer. F - C (plagal Amen) twice, soft choir and strings, one long final chord
    for b, ch, r, d in [(13.7, ["A3", "C4", "F4"], "F2", 2), (15.7, ["G3", "C4", "E4"], "C2", 2),
                        (17.7, ["A3", "C4", "F4"], "F2", 1.5), (19.2, ["G3", "C4", "E4", "G4"], "C2", 2.5)]:
        choir.chord(b, [note(p) for p in ch], d, 64, 3); strs.chord(b, [note(p) - 12 for p in ch], d, 48, 3); bass.add(b, r, d, 56)
    for k, p in enumerate(["C4", "E4", "G4", "C5", "E5", "G5"]): harp.add(19.2 + k * 0.18, p, 2.2, 56)
    finish_all(tpt, horn, strs, timp, glock, choir, harp, bass, drums)
    return mid

def victory_chime_midi(secs):
    bpm = 150; mid = new_mid(bpm)
    cel = Track(mid, 0, CELESTA, "celesta", 100, 64, 80); glock = Track(mid, 1, GLOCK, "glock", 86, 76, 80)
    harp = Track(mid, 2, HARP, "harp", 90, 52, 80)
    run = ["C5", "E5", "G5", "C6", "E6", "G6", "C7"]
    for k, p in enumerate(run):
        cel.add(k * 0.22, p, 2.2, 100); glock.add(k * 0.22 + 0.03, p, 1.6, 74); harp.add(k * 0.18, note(p) - 12, 1.6, 70)
    cel.chord(1.6, [note("C6"), note("E6"), note("G6")], 2.2, 84)
    finish_all(cel, glock, harp)
    return mid

# ----------------------------------------------------------------------------------------------- audio helpers
def run(cmd): return subprocess.run(cmd, check=True, capture_output=True, text=True)

def render_midi(mid):
    """MIDI -> mono float32 at SR via FluidSynth."""
    tmp = tempfile.mkdtemp(); midp, raw = f"{tmp}/x.mid", f"{tmp}/x.wav"; mid.save(midp)
    run(["fluidsynth", "-ni", "-g", "0.5", "-r", str(SR), "-O", "float", "-T", "wav", "-F", raw, DLS, midp])
    sr, x = wavfile.read(raw); assert sr == SR
    x = x.astype(np.float32); return x.mean(axis=1) if x.ndim == 2 else x

def fit(x, secs, fade_in=0.0, fade_out=0.3):
    n = int(round(secs * SR)); y = np.zeros(n, np.float32); y[:min(n, len(x))] = x[:n]
    if fade_in > 0: k = int(fade_in * SR); y[:k] *= np.linspace(0, 1, k)
    if fade_out > 0: k = int(fade_out * SR); y[-k:] *= np.linspace(1, 0, k) ** 2
    return y

def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).round().astype(np.int16))
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-b:a", "96k", path[:-4] + ".mp3"])

def measure(path):
    """EBU R128 integrated loudness (LUFS), true peak (dBTP) and sample peak (dBFS) via ffmpeg."""
    err = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true+sample", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summ = err[err.rfind("Summary:"):]
    get = lambda pat: float(re.search(pat, summ, re.S).group(1))
    return dict(lufs=get(r"I:\s+(-?[\d.]+|-inf) LUFS"), truePeak=get(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf)"),
                samplePeak=get(r"Sample peak:\s+Peak:\s+(-?[\d.]+|-inf)"))

def probe_secs(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout.strip())

def normalize_lufs(x, target, tp_ceiling=-1.0):
    """Gain to an integrated loudness target, measured by ffmpeg (two passes), never pushing true peak over the ceiling."""
    tmp = tempfile.mkdtemp() + "/m.wav"
    for _ in range(2):
        wavfile.write(tmp, SR, x.astype(np.float32)); m = measure(tmp)
        g = target - m["lufs"]
        if m["truePeak"] + g > tp_ceiling:                    # soft-clip the few loudest transients instead of losing loudness
            x = np.tanh(x * 10 ** (g / 20) / 10 ** (tp_ceiling / 20) * 0.9) * 10 ** (tp_ceiling / 20) / 0.9 / 10 ** (g / 20)
        x = x * 10 ** (g / 20)
    return x.astype(np.float32)

def peak_normalize(x, db):
    return (x / (np.max(np.abs(x)) + 1e-12) * 10 ** (db / 20)).astype(np.float32)

# ----------------------------------------------------------------------------------------------- sfx synthesis
def t_axis(secs): return np.arange(int(secs * SR)) / SR
def noise(n): return RNG.standard_normal(n).astype(np.float32)
def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)
def lp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, "lowpass", fs=SR, output="sos"), x)
def hp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, "highpass", fs=SR, output="sos"), x)
def env_exp(n, tau, delay=0): t = np.arange(n) / SR - delay; return np.where(t >= 0, np.exp(-np.maximum(t, 0) / tau), 0)
def place(dst, src, at):
    i = int(at * SR); n = min(len(src), len(dst) - i)
    if n > 0: dst[i:i + n] += src[:n]
def sweep(f0, f1, secs, curve=1.0):
    t = t_axis(secs); f = f0 + (f1 - f0) * (t / secs) ** curve; return np.sin(2 * np.pi * np.cumsum(f) / SR)

def resonator(x, f, bw):
    r = np.exp(-np.pi * bw / SR); c = np.cos(2 * np.pi * f / SR)
    return signal.lfilter([1 - r], [1, -2 * r * c, r * r], x)

def reverb(x, secs=0.8, wet=0.25, bright=4000):
    ir = noise(int(secs * SR)) * env_exp(int(secs * SR), secs / 6.0); ir = lp(ir, bright)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    y = signal.fftconvolve(x, ir)[:len(x) + int(secs * SR)]
    out = np.zeros(len(y)); out[:len(x)] += x * (1 - wet); out += y * wet; return out

VOWELS = {"a": [(750, 90), (1200, 110), (2600, 160)], "o": [(500, 80), (850, 100), (2500, 160)],
          "e": [(450, 80), (2000, 120), (2700, 160)], "eh": [(580, 80), (1800, 120), (2600, 160)],
          "ah": [(680, 90), (1100, 110), (2450, 160)], "u": [(350, 70), (800, 90), (2300, 150)]}

def glottal(f0_curve, rough=0.0, am_hz=0.0, am_depth=0.0):
    """Band-limited sawtooth-like source following an f0 curve (Hz per sample)."""
    ph = np.cumsum(f0_curve) / SR; x = np.zeros(len(f0_curve))
    fmax = np.max(f0_curve)
    for k in range(1, int(5000 / max(40, np.min(f0_curve))) + 1):
        if k * np.min(f0_curve) > 6000: break
        mask = (k * f0_curve < 6500)
        x += mask * np.sin(2 * np.pi * k * ph) / k ** 1.1
    if rough: x *= 1 + rough * lp(noise(len(x)), 60) * 3
    if am_hz: x *= 1 - am_depth * (0.5 + 0.5 * np.sin(2 * np.pi * am_hz * np.arange(len(x)) / SR))
    return x

def vocal(f0_curve, vowel, amp, breath=0.08, fscale=1.0, **kw):
    src = glottal(f0_curve, **kw) + breath * noise(len(f0_curve)) * 4
    y = sum(resonator(src, f * fscale, bw * fscale) * g for (f, bw), g in zip(VOWELS[vowel], (1.0, 0.6, 0.25)))
    return y * amp

def adsr(n, a, d_tau, hold=0.0):
    t = np.arange(n) / SR
    return np.where(t < a, t / max(a, 1e-4), np.where(t < a + hold, 1.0, np.exp(-(t - a - hold) / d_tau)))

def smooth_rand(n, rate_hz, lo=0.0, hi=1.0):
    k = max(2, int(n / SR * rate_hz) + 2); pts = RNG.uniform(lo, hi, k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)

def babble(secs, voices, f0_lo, f0_hi, syll_hz=4.0, vowels=("a", "o", "e", "eh", "u")):
    n = int(secs * SR); out = np.zeros(n)
    for _ in range(voices):
        f0 = RNG.uniform(f0_lo, f0_hi) * (1 + 0.08 * (smooth_rand(n, 2) - 0.5))
        src = glottal(f0) + 0.05 * noise(n)
        v1, v2 = RNG.choice(vowels, 2, replace=False)
        y1 = sum(resonator(src, f, bw) * g for (f, bw), g in zip(VOWELS[v1], (1, .6, .25)))
        y2 = sum(resonator(src, f, bw) * g for (f, bw), g in zip(VOWELS[v2], (1, .6, .25)))
        mix = smooth_rand(n, syll_hz * 1.3)
        syl = np.clip(smooth_rand(n, syll_hz * 2, -0.6, 1.0), 0, 1) ** 1.5
        out += (y1 * mix + y2 * (1 - mix)) * syl * RNG.uniform(0.4, 1.0)
    return lp(out, 3200)

def metal(secs, freqs, taus, amps, strike=0.003):
    n = int(secs * SR); t = t_axis(secs); y = np.zeros(n)
    for f, tau, a in zip(freqs, taus, amps):
        y += a * np.sin(2 * np.pi * f * t + RNG.uniform(0, 6.28)) * np.exp(-t / tau)
        y += 0.5 * a * np.sin(2 * np.pi * f * 1.003 * t) * np.exp(-t / tau)   # slight beating
    y += hp(noise(n), 2000) * env_exp(n, strike) * 0.6
    return y

def thud(secs, f0, f1, tau, sweep_secs=0.3, click=0.2):
    n = int(secs * SR); s = np.zeros(n); sw = sweep(f0, f1, min(sweep_secs, secs), 0.5); s[:len(sw)] = sw
    if len(sw) < n: s[len(sw):] = np.sin(2 * np.pi * f1 * t_axis(secs)[len(sw):])
    return s * env_exp(n, tau) + click * lp(noise(n), 400) * env_exp(n, 0.02)

def grains(secs, count, lo, hi, tau, span, level=1.0):
    n = int(secs * SR); y = np.zeros(n); g = int(tau * 8 * SR)
    for _ in range(count):
        at = RNG.uniform(*span); f = RNG.uniform(lo, hi)
        gr = resonator(noise(g), f, f * 0.15) * env_exp(g, tau) * RNG.uniform(0.3, 1.0)
        place(y, gr, at)
    return y * level

def sfx_crowd_murmur():
    secs = 8.0; y = babble(secs, 26, 100, 230, 4.5)
    y = reverb(y, 1.0, 0.35)[:int(secs * SR)]
    return fit(y, secs, fade_in=0.8, fade_out=2.5)

def sfx_crowd_gasp():
    secs = 1.6; n = int(secs * SR); y = np.zeros(n)
    for _ in range(16):                                        # breathy inhaled "hah"
        m = int(0.6 * SR); e = adsr(m, 0.06, 0.18)
        place(y, vocal(np.full(m, RNG.uniform(180, 320)), "ah", 1.0, breath=0.9) * e * 0.2
              + resonator(noise(m), 1100, 600) * e * RNG.uniform(0.6, 1.0), RNG.uniform(0, 0.15))
    for _ in range(8):                                         # a few voiced "oh!"
        m = int(0.45 * SR); f0 = np.linspace(RNG.uniform(200, 260), RNG.uniform(280, 360), m)
        place(y, vocal(f0, "o", 1.0, breath=0.2) * adsr(m, 0.03, 0.12), RNG.uniform(0.08, 0.3))
    y = lp(reverb(y, 0.9, 0.3)[:n], 4000)
    return fit(y, secs, fade_out=0.4)

def sfx_crowd_cheer():
    secs = 4.0; n = int(secs * SR); y = np.zeros(n)
    for _ in range(26):                                        # "hooray / yay"
        m = int(RNG.uniform(0.6, 1.1) * SR); f0 = RNG.uniform(220, 360) * np.interp(np.arange(m), [0, m * 0.3, m], [0.9, 1.15, 0.95])
        v = "e" if RNG.random() < 0.5 else "eh"
        for k in range(int(RNG.integers(1, 4))):
            place(y, vocal(f0, v, 1.0, breath=0.15) * adsr(m, 0.05, 0.25, 0.15) * RNG.uniform(0.3, 1.0), RNG.uniform(0, 2.4) + k * 0.9)
    clap = np.zeros(n); g = int(0.02 * SR)
    for _ in range(900):                                       # applause
        at = RNG.uniform(0.1, secs); place(clap, bp(noise(g), 900, 5000) * env_exp(g, 0.004) * RNG.uniform(0.2, 1), at)
    y = lp(y, 3500) / (np.max(np.abs(y)) + 1e-9) + clap / (np.max(np.abs(clap)) + 1e-9) * 0.5
    y = reverb(y, 1.0, 0.3)[:n]
    return fit(y, secs, fade_in=0.15, fade_out=1.6)

def sfx_giant_step():
    secs = 1.0; n = int(secs * SR)
    y = thud(secs, 75, 32, 0.28, 0.35, click=0.5)
    y += lp(noise(n), 160) * env_exp(n, 0.25) * 0.8                               # rumble
    y += grains(secs, 40, 800, 3500, 0.006, (0.0, 0.18), 0.25)                     # gravel crunch
    return fit(y, secs, fade_out=0.2)

def sfx_run_steps():
    secs = 1.7; n = int(secs * SR); y = np.zeros(n)
    for k in range(6):                                         # light running feet, ~0.27 s apart
        m = int(0.25 * SR); s = thud(0.25, 160, 85, 0.05, 0.06, click=0.25) * (1.0 if k % 2 == 0 else 0.8)
        s += grains(0.25, 10, 1500, 5000, 0.004, (0.0, 0.04), 0.4)
        place(y, s, 0.03 + k * 0.27)
    return fit(y, secs, fade_out=0.1)

def sfx_spear_clang():
    secs = 1.6
    y = metal(secs, [433, 1102, 1876, 2780, 3913, 5200], [0.9, 0.6, 0.45, 0.32, 0.22, 0.14], [1.0, 0.7, 0.5, 0.35, 0.25, 0.15])
    y += thud(secs, 140, 90, 0.08, 0.05, click=0.0) * 0.6                        # spear butt hits the shield/ground
    return fit(reverb(y, 0.8, 0.2), secs, fade_out=0.3)

def sfx_armour_clank():
    secs = 1.3; n = int(secs * SR); y = np.zeros(n)
    for at, base in ((0.0, 310), (0.12, 470), (0.3, 260), (0.45, 390)):
        fr = [base, base * 2.43, base * 3.9, base * 5.7]
        place(y, metal(0.6, fr, [0.25, 0.18, 0.12, 0.08], [1, .6, .4, .25], 0.002) * RNG.uniform(0.6, 1.0), at)
    y += grains(secs, 45, 4000, 8000, 0.01, (0.0, 0.7), 0.6)                        # chain-mail jingle
    place(y, thud(0.6, 150, 80, 0.1, 0.08, click=0.3) * 0.8, 0.55)                  # set down on the ground
    return fit(reverb(y, 0.6, 0.18), secs, fade_out=0.25)

def sfx_water_splash():
    secs = 1.2; n = int(secs * SR); y = bp(noise(n), 500, 4500) * env_exp(n, 0.12) * 0.8
    t = t_axis(0.12)
    for _ in range(28):                                        # bubbles: rising decaying sines
        f0 = RNG.uniform(400, 1600); tau = RNG.uniform(0.015, 0.05)
        b = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 3.5 * t)) / SR) * np.exp(-t / tau)
        place(y, b * RNG.uniform(0.3, 1.0), RNG.exponential(0.15))
    y += bp(noise(n), 1500, 6000) * env_exp(n, 0.4, 0.1) * 0.12                    # trickle
    return fit(reverb(y, 0.5, 0.15), secs, fade_out=0.3)

def sfx_stone_clack():
    secs = 0.3; n = int(secs * SR); x = noise(n) * env_exp(n, 0.002)
    y = resonator(x, 2600, 300) + 0.7 * resonator(x, 4100, 450) + 0.5 * resonator(x, 950, 120)
    return fit(y, secs, fade_out=0.05)

def sfx_sling_whoosh():
    """Seamless loop: 5 turns of 0.5 s (sling_windup is 1 turn per ~0.5 s); 2.5 s covers 70.2-72.6 s."""
    period, turns, secs = 0.5, 5, 2.5; n = int(secs * SR); ext = int(period * SR); m = n + ext
    t = np.arange(m) / SR; phase = (t % period) / period
    e = np.sin(np.pi * phase) ** 4                                                  # one pass of the pouch per turn
    nz = noise(m); low, high = bp(nz, 250, 900), bp(nz, 900, 3000)
    y = e * (low * (1 - e) + high * e * 1.3)
    y += 0.12 * np.sin(2 * np.pi * 95 * t) * (0.5 + 0.5 * e) * lp(noise(m), 30) * 4  # cord whirr
    y = y.astype(np.float64); fade = np.linspace(0, 1, ext)
    y[:ext] = y[:ext] * fade + y[n:n + ext] * (1 - fade)                           # wrap the tail onto the head
    return y[:n].astype(np.float32)

def sfx_sling_snap():
    secs = 0.75; n = int(secs * SR); y = np.zeros(n)
    m = int(0.05 * SR); crack = hp(noise(m), 1500) * env_exp(m, 0.003) * 0.6 + 0.4 * np.sin(2 * np.pi * 2100 * t_axis(0.05)) * env_exp(m, 0.008)
    place(y, crack, 0.15)                                      # stone leaves the pouch 0.15 s into sling_release
    k = int(0.5 * SR); wt = np.arange(k) / k                    # stone whoosh flying away (0.45 s flight)
    nz = noise(k); w = (bp(nz, 1200, 4000) * wt + bp(nz, 600, 1500) * (1 - wt)) * np.sin(np.pi * wt) ** 2 * 1.6
    place(y, w, 0.17)
    return fit(y, secs, fade_out=0.1)

def sfx_stone_hit():
    secs = 0.9; n = int(secs * SR)
    y = thud(secs, 230, 140, 0.11, 0.08, click=0.6)                                # the "bonk"
    x = noise(n) * env_exp(n, 0.002)
    y += 1.2 * resonator(x, 520, 40) + 0.8 * resonator(x, 1350, 80)                # hollow wood-block body
    y += 0.25 * np.sin(2 * np.pi * 1810 * t_axis(secs)) * env_exp(n, 0.25)         # small helmet ring
    return fit(y, secs, fade_out=0.2)

def sfx_giant_fall():
    secs = 2.4; n = int(secs * SR)
    y = thud(secs, 60, 26, 0.7, 0.6, click=1.0) * 1.2
    y += lp(noise(n), 140) * env_exp(n, 0.9) * 1.4                                  # long rumble
    y += grains(secs, 60, 2500, 7000, 0.012, (0.0, 0.7), 0.35)                      # armour rattle
    y += grains(secs, 50, 600, 2500, 0.008, (0.0, 0.35), 0.4)                       # dust and gravel
    return fit(reverb(y, 1.0, 0.2), secs, fade_out=0.6)

def sfx_goliath_roar():
    secs = 1.5; n = int(secs * SR)
    f0 = np.interp(np.arange(n), [0, n * 0.25, n * 0.7, n], [80, 115, 100, 70])
    y = vocal(f0, "ah", 1.0, breath=0.35, fscale=0.82, rough=0.4, am_hz=24, am_depth=0.35)
    y += 0.5 * vocal(f0 / 2, "o", 1.0, breath=0.1, fscale=0.8)                     # sub-octave for size
    y *= adsr(n, 0.12, 0.5, 0.6)
    return fit(reverb(y, 0.9, 0.22), secs, fade_out=0.3)

def sfx_goliath_laugh():
    secs = 1.7; n = int(secs * SR); y = np.zeros(n)
    for k, f in enumerate((112, 104, 96, 88, 80)):              # "HA ha ha ha ha", falling, big and silly
        m = int(0.26 * SR); f0 = np.linspace(f * 1.08, f * 0.94, m)
        s = vocal(f0, "ah", 1.0, breath=0.25, fscale=0.85) * adsr(m, 0.04, 0.09, 0.05)
        h = int(0.05 * SR); s[:h] += resonator(noise(h), 1100, 500) * np.linspace(0.6, 0, h) * 0.6   # the "h"
        place(y, s * (1.0 - k * 0.1), 0.02 + k * 0.3)
    return fit(reverb(y, 0.8, 0.2), secs, fade_out=0.2)

def sfx_sheep_baa():
    secs = 1.1; n = int(secs * SR); t = t_axis(secs)
    f0 = np.interp(np.arange(n), [0, n * 0.15, n], [300, 360, 330]) * (1 + 0.035 * np.sin(2 * np.pi * 8.5 * t))
    y = vocal(f0, "eh", 1.0, breath=0.2, am_hz=8.5, am_depth=0.7)                 # the bleat tremolo
    y *= adsr(n, 0.05, 0.25, 0.45)
    return fit(reverb(y, 0.7, 0.18), secs, fade_out=0.15)

def sfx_lion_roar():
    secs = 1.7; n = int(secs * SR)
    f0 = np.interp(np.arange(n), [0, n * 0.2, n], [130, 175, 95])
    y = vocal(f0, "o", 1.0, breath=0.6, fscale=0.9, rough=0.6, am_hz=30, am_depth=0.4) * adsr(n, 0.18, 0.5, 0.5)
    return fit(reverb(lp(y, 3000), 1.0, 0.25), secs, fade_out=0.3)

def sfx_bear_growl():
    secs = 1.5; n = int(secs * SR)
    f0 = np.interp(np.arange(n), [0, n * 0.3, n], [62, 78, 58])
    y = vocal(f0, "u", 1.0, breath=0.5, fscale=0.8, rough=0.7, am_hz=17, am_depth=0.55) * adsr(n, 0.2, 0.45, 0.5)
    return fit(reverb(lp(y, 2200), 0.8, 0.2), secs, fade_out=0.3)

def sfx_victory_chime():
    return fit(render_midi(victory_chime_midi(2.2)), 2.4, fade_out=0.5)

SFX = {"crowd_murmur": sfx_crowd_murmur, "giant_step": sfx_giant_step, "spear_clang": sfx_spear_clang,
       "goliath_roar": sfx_goliath_roar, "crowd_gasp": sfx_crowd_gasp, "goliath_laugh": sfx_goliath_laugh,
       "sheep_baa": sfx_sheep_baa, "lion_roar": sfx_lion_roar, "bear_growl": sfx_bear_growl,
       "armour_clank": sfx_armour_clank, "water_splash": sfx_water_splash, "stone_clack": sfx_stone_clack,
       "run_steps": sfx_run_steps, "sling_whoosh": sfx_sling_whoosh, "sling_snap": sfx_sling_snap,
       "stone_hit": sfx_stone_hit, "giant_fall": sfx_giant_fall, "crowd_cheer": sfx_crowd_cheer,
       "victory_chime": sfx_victory_chime}
# Recommended playback gain (dB) on top of the -3 dBFS-peak files, so beds sit under the voice and hits stay big.
SFX_GAIN = {"crowd_murmur": -12, "crowd_gasp": -6, "crowd_cheer": -8, "giant_step": -2, "spear_clang": -6,
            "goliath_roar": -4, "goliath_laugh": -6, "sheep_baa": -8, "lion_roar": -6, "bear_growl": -6,
            "armour_clank": -6, "water_splash": -8, "stone_clack": -10, "run_steps": -8, "sling_whoosh": -8,
            "sling_snap": -6, "stone_hit": 0, "giant_fall": 0, "victory_chime": -6}
LOOP_SFX = {"sling_whoosh"}

MUSIC = {"theme_tension": theme_tension, "theme_shepherd": theme_shepherd, "theme_faith": theme_faith,
         "theme_battle": theme_battle, "sting_hit": sting_hit, "theme_victory": theme_victory}

def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        last = i + 1 == len(cues); sting = c["cue"].startswith("sting")
        # Every cue but the last carries a 0.6 s tail for the crossfade; a sting rings into the following silence.
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3),
                        secs=round(end - c["t"] + (0 if (last or sting) else XFADE), 3), sting=sting, last=last))
    return out

# ----------------------------------------------------------------------------------------------- build
def build_music(tl):
    manifest = []
    for c in cue_spans(tl):
        assert c["cue"] in MUSIC, f"no composer for cue {c['cue']}"
        x = render_midi(MUSIC[c["cue"]](c["secs"]))
        x = fit(x, c["secs"], fade_out=2.5 if c["last"] else (0.6 if c["sting"] else 0.3))
        x = hp(x, 25).astype(np.float32)
        x = normalize_lufs(x, MUSIC_LUFS)
        path = f"{MUSIC_DIR}/{c['cue']}.wav"; write_wav(path, x); m = measure(path)
        manifest.append(dict(cue=c["cue"], t=c["t"], span=c["span"], secs=round(probe_secs(path), 3),
                             loop=False, oneShot=c["sting"], **{k: round(v, 1) for k, v in m.items()}))
        print(f"music {c['cue']:15s} t={c['t']:6.2f} span={c['span']:6.2f} file={manifest[-1]['secs']:6.2f}s "
              f"I={m['lufs']:6.1f} LUFS TP={m['truePeak']:5.1f} dBTP")
    json.dump(dict(rule="Start each cue at its timeline t at full level; fade the previous cue out over 0.6 s from that t. "
                        "Each non-final cue is its span + 0.6 s long so the fade has material. sting_hit is a one-shot "
                        "followed by silence until theme_victory. Music sits at -20 LUFS; duck it ~6 dB under voice lines.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, cues=manifest),
              open(f"{MUSIC_DIR}/cues.json", "w"), indent=1, ensure_ascii=False)

def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        x = SFX[sid](); x = hp(np.asarray(x, np.float64), 25)
        x = peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; write_wav(path, x); m = measure(path)
        manifest.append(dict(id=sid, secs=round(probe_secs(path), 3), loop=sid in LOOP_SFX, gainDb=SFX_GAIN[sid],
                             **{k: round(v, 1) for k, v in m.items()}))
        print(f"sfx   {sid:15s} {manifest[-1]['secs']:5.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}")
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play at gainDb (recommended mix level). "
                        "sling_whoosh is a seamless 2.5 s loop (5 sling turns); stop it at sling_release.",
                   peakDbfs=SFX_PEAK_DB, sfx=manifest),
              open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)

def load(path):
    sr, x = wavfile.read(path); assert sr == SR, path
    x = x.astype(np.float32) / (32768 if x.dtype == np.int16 else 1)
    return x.mean(axis=1) if x.ndim == 2 else x

def build_preview(tl):
    n = int((tl["duration"] + 1.0) * SR); mus = np.zeros(n); fx = np.zeros(n); vo = np.zeros(n)
    cues = cue_spans(tl)
    for i, c in enumerate(cues):
        x = load(f"{MUSIC_DIR}/{c['cue']}.wav").astype(np.float64)
        if not c["last"] and not c["sting"]:                       # fade out where the next cue starts
            k0 = int(c["span"] * SR); k = int(XFADE * SR); x[k0:k0 + k] *= np.linspace(1, 0, len(x[k0:k0 + k])); x[k0 + k:] = 0
        place(mus, x, c["t"])
    gains = SFX_GAIN; voice_lines = 0
    for s in tl["sfx"]:
        x = load(f"{SFX_DIR}/{s['id']}.wav") * 10 ** (gains[s["id"]] / 20)
        if s["id"] in LOOP_SFX:                                     # stop the loop at the next sling_snap (release)
            stop = min([o["t"] for o in tl["sfx"] if o["id"] == "sling_snap" and o["t"] > s["t"]] or [s["t"] + len(x) / SR])
            k = int((stop - s["t"]) * SR); x = np.tile(x, k // len(x) + 1)[:k].copy(); f = int(0.05 * SR); x[-f:] *= np.linspace(1, 0, f)
        place(fx, x, s["t"])
    lang = "en"
    for line in tl["lines"]:
        p = f"{VOICE_DIR}/{lang}/{line['id']}.wav"
        if os.path.exists(p):
            v = load(p) if wavfile.read(p)[0] == SR else None
            if v is not None: place(vo, v, line["t"]); voice_lines += 1
    if voice_lines:                                                 # duck music 6 dB under the voice
        env = lp(np.abs(vo), 4) > 0.01; duck = np.where(env, 10 ** (-6 / 20), 1.0)
        duck = signal.lfilter([0.0005], [1, -0.9995], duck - 1) + 1; mus *= duck
    mix = (mus + fx + vo).astype(np.float32)
    tmp = tempfile.mkdtemp() + "/mix.wav"; wavfile.write(tmp, SR, mix)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", "alimiter=limit=0.89:level=false",
         "-ac", "1", "-ar", str(SR), "-b:a", "96k", PREVIEW])
    m = measure(PREVIEW)
    print(f"preview {probe_secs(PREVIEW):.2f}s I={m['lufs']:.1f} LUFS TP={m['truePeak']:.1f} dBTP, voice lines included: {voice_lines} ({lang})")
    return voice_lines

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--skip-music", action="store_true")
    ap.add_argument("--skip-sfx", action="store_true"); ap.add_argument("--skip-preview", action="store_true")
    a = ap.parse_args()
    assert os.path.exists(DLS), "GM bank not found at " + DLS
    tl = json.load(open(TIMELINE))
    if not a.skip_music: build_music(tl)
    if not a.skip_sfx: build_sfx(tl)
    if not a.skip_preview: build_preview(tl)
