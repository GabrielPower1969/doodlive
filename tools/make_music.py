#!/usr/bin/env python3
"""Score and stingers for the angel, composed as MIDI and rendered with FluidSynth + macOS's General MIDI bank
(gs_instruments.dls, ships with CoreAudio; no download). Replaces the WebAudio synth sounds.

  theme   40 s loop — harp arpeggios, string pad, choir, glockenspiel melody (F major, 72 bpm)
  fanfare 2.6 s — trumpet + horn call with timpani (the Blow action)
  chime   1.6 s — celesta/glockenspiel run (the reveal)
  swell   2.4 s — choir + strings crescendo (she rises out of the page)

Outputs web/assets/music/*.mp3 and unity/Assets/DoodLive/Audio/*.wav (fanfare.wav / chime.wav overwrite the synth ones).
Usage: python3 tools/make_music.py [--out-dir DIR]   (needs: pip install mido; brew install fluid-synth; ffmpeg)
"""
import os, subprocess, sys, tempfile
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLS = "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls"
WEB, UNITY = f"{ROOT}/web/assets/music", f"{ROOT}/unity/Assets/DoodLive/Audio"
TPB = 480
N = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)
def note(name):  # "F4" -> 65
    return 12 * (int(name[-1]) + 1) + N[name[0]] + (1 if "#" in name else -1 if "b" in name else 0)

class Track:
    def __init__(self, mid, ch, program, name, vol=100, pan=64, reverb=60):
        self.t = MidiTrack(); mid.tracks.append(self.t); self.ch = ch; self.events = []
        self.t.append(MetaMessage("track_name", name=name, time=0))
        if ch != 9: self.t.append(Message("program_change", channel=ch, program=program, time=0))
        for cc, v in ((7, vol), (10, pan), (91, reverb)): self.t.append(Message("control_change", channel=ch, control=cc, value=v, time=0))
    def add(self, beat, pitch, dur, vel=90):
        on, off = int(beat * TPB), int((beat + dur) * TPB)
        self.events.append((on, 1, pitch, vel)); self.events.append((off, 0, pitch, 0))
    def finish(self):
        last = 0
        for tick, kind, pitch, vel in sorted(self.events, key=lambda e: (e[0], e[1])):
            self.t.append(Message("note_on" if kind else "note_off", channel=self.ch, note=pitch, velocity=vel, time=tick - last)); last = tick
        self.t.append(MetaMessage("end_of_track", time=0))

def new_mid(bpm):
    mid = MidiFile(ticks_per_beat=TPB); meta = MidiTrack(); mid.tracks.append(meta)
    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(bpm), time=0)); meta.append(MetaMessage("end_of_track", time=0)); return mid

def theme():
    mid = new_mid(72)
    harp = Track(mid, 0, 46, "harp", 92, 54, 70); pad = Track(mid, 1, 48, "strings", 70, 70, 80)
    choir = Track(mid, 2, 52, "choir", 60, 64, 90); glock = Track(mid, 3, 9, "glockenspiel", 78, 80, 70)
    bass = Track(mid, 4, 32, "bass", 55, 60, 30)
    # F  C/E  Dm  Bb  (I V vi IV) x2, then Bb C F F (plagal lift), 4 beats each -> 12 bars = 40 s
    chords = [("F", ["F3", "C4", "F4", "A4"]), ("C", ["E3", "C4", "E4", "G4"]), ("Dm", ["D3", "A3", "F4", "A4"]), ("Bb", ["Bb2", "F3", "D4", "F4"])] * 2 \
           + [("Bb", ["Bb2", "F3", "D4", "F4"]), ("C", ["C3", "G3", "E4", "G4"]), ("F", ["F3", "C4", "F4", "A4"]), ("F", ["F3", "C4", "F4", "A4"])]
    for i, (name, tones) in enumerate(chords):
        b = i * 4
        pitches = [note(t) for t in tones]
        for k, p in enumerate(pitches): pad.add(b, p, 4, 58 - k * 3)                       # pad holds the chord
        bass.add(b, pitches[0] - 12, 3.8, 70)
        arp = pitches + [pitches[1] + 12, pitches[2] + 12] + pitches[::-1][:2]             # up-and-down arpeggio, 8ths
        for k, p in enumerate(arp): harp.add(b + k * 0.5, p, 0.6, 74 + (10 if k == 0 else 0))
        if i >= 4:                                                                         # choir joins on the repeat
            for k, p in enumerate(pitches[1:]): choir.add(b, p + 12, 4, 46 - k * 4)
    # glockenspiel melody (F major), gentle, with rests
    mel = [(0, "A5", 1), (1, "C6", 1), (2, "F6", 2), (4, "E6", 1.5), (5.5, "D6", 0.5), (6, "C6", 2),
           (8, "A5", 1), (9, "D6", 1), (10, "F6", 1), (11, "A6", 1), (12, "G6", 2), (14, "F6", 2),
           (18, "C6", 1), (19, "D6", 1), (20, "E6", 2), (22, "F6", 2), (24, "G6", 1.5), (25.5, "A6", 0.5), (26, "F6", 2), (28, "E6", 1), (29, "C6", 3),
           (32, "F6", 2), (34, "G6", 1), (35, "A6", 1), (36, "G6", 2), (38, "F6", 2), (40, "A6", 1), (41, "C7", 1), (42, "A6", 2), (44, "F6", 4)]
    for b, p, d in mel: glock.add(b, note(p), d, 84)
    for t in (harp, pad, choir, glock, bass): t.finish()
    return mid, 40.0

def fanfare():
    mid = new_mid(120)
    tpt = Track(mid, 0, 56, "trumpet", 100, 60, 55); horn = Track(mid, 1, 60, "horn", 85, 70, 70); timp = Track(mid, 2, 47, "timpani", 95, 64, 60)
    seq = [(0, "G4", 0.4), (0.5, "C5", 0.4), (1.0, "E5", 0.4), (1.5, "G5", 1.0), (2.6, "E5", 0.35), (3.0, "G5", 2.0)]
    for b, p, d in seq: tpt.add(b, note(p), d, 112); horn.add(b, note(p) - 12, d, 88)
    for b, p in ((0, "C3"), (1.5, "G2"), (3.0, "C3")): timp.add(b, note(p), 0.8, 110)
    for t in (tpt, horn, timp): t.finish()
    return mid, 2.6

def chime():
    mid = new_mid(140)
    cel = Track(mid, 0, 8, "celesta", 95, 64, 80); glock = Track(mid, 1, 9, "glock", 80, 74, 80)
    for k, p in enumerate(["C6", "E6", "G6", "C7", "E7", "G7"]): cel.add(k * 0.25, note(p), 1.5, 96); glock.add(k * 0.25 + 0.05, note(p), 1.2, 70)
    cel.finish(); glock.finish(); return mid, 1.6

def swell():
    mid = new_mid(60)
    choir = Track(mid, 0, 52, "choir", 100, 64, 95); strs = Track(mid, 1, 48, "strings", 90, 60, 90)
    for k, p in enumerate(["F3", "C4", "F4", "A4", "C5"]): choir.add(0.0, note(p), 2.2, 40 + k * 12); strs.add(0.0, note(p) + 12, 2.3, 50 + k * 8)
    choir.finish(); strs.finish(); return mid, 2.4

def render(name, build, loop=False):
    mid, secs = build(); tmp = tempfile.mkdtemp()
    midp, raw = f"{tmp}/{name}.mid", f"{tmp}/{name}.wav"; mid.save(midp)
    subprocess.run(["fluidsynth", "-ni", "-g", "0.9", "-r", "44100", "-F", raw, DLS, midp], check=True, capture_output=True)
    os.makedirs(WEB, exist_ok=True); os.makedirs(UNITY, exist_ok=True)
    tail = "" if loop else ",afade=t=out:st=%s:d=0.4" % (secs - 0.4)
    af = f"atrim=0:{secs + (0 if loop else 0.4)},loudnorm=I=-18:TP=-1.5{tail}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", af, "-ac", "2", "-ar", "44100", f"{UNITY}/{name}.wav"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{UNITY}/{name}.wav", "-b:a", "128k", f"{WEB}/{name}.mp3"], check=True)
    print(f"{name:8s} {secs:5.1f}s -> {UNITY}/{name}.wav, {WEB}/{name}.mp3")

if __name__ == "__main__":
    assert os.path.exists(DLS), "GM bank not found at " + DLS
    render("theme", theme, loop=True); render("fanfare", fanfare); render("chime", chime); render("swell", swell)
