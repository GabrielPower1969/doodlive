#!/usr/bin/env python3
"""Bake the web prototype's sounds into files for the Unity app.

fanfare.wav / chime.wav: offline port of the WebAudio synth in web/audio.js.
voice_*.wav: the same lines app.js speaks, rendered with macOS `say` (Tingting, zh_CN).
Output: unity/Assets/DoodLive/Audio/. Re-run after changing a line or the synth.
"""
import os
import subprocess
import wave

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "unity", "Assets", "DoodLive", "Audio")

VOICES = {
    "voice_hello": "哇！我活过来啦！谢谢你给我涂上这么漂亮的颜色！",
    "voice_0": "听！天堂的号角为你吹响！",
    "voice_1": "你画得真好看，我好喜欢这些颜色！",
    "voice_2": "愿你今天平安、快乐！",
    "voice_3": "再给我画一件新衣服吧！",
}


def ramp(t, pts):
    """Piecewise-linear automation like AudioParam.linearRampToValueAtTime."""
    xs, ys = zip(*pts)
    return np.interp(t, xs, ys)


def lowpass(x, cutoff, q):
    """Time-varying biquad low-pass (RBJ), cutoff per sample."""
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        w0 = 2 * np.pi * cutoff[i] / SR
        alpha = np.sin(w0) / (2 * q)
        cw = np.cos(w0)
        b0 = (1 - cw) / 2
        b1 = 1 - cw
        a0 = 1 + alpha
        a1 = -2 * cw
        a2 = 1 - alpha
        v = (b0 * x[i] + b1 * x1 + b0 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, x[i], y1, v
        y[i] = v
    return y


def saw(phase):
    return 2 * (phase - np.floor(phase + 0.5))


def square(phase):
    return np.sign(np.sin(2 * np.pi * phase))


def brass(freq, dur):
    n = int((dur + 0.05) * SR)
    t = np.arange(n) / SR
    vib = freq * 0.006 * np.sin(2 * np.pi * 5.5 * t)
    sig = np.zeros(n)
    for kind, mul, gain in (("saw", 1, 1), ("square", 1.002, 0.4), ("saw", 2, 0.25)):
        phase = np.cumsum((freq * mul + vib) / SR)
        sig += gain * (saw(phase) if kind == "saw" else square(phase))
    cutoff = ramp(t, [(0, 600), (0.06, 3200), (dur, 2000), (dur + 1, 2000)])
    sig = lowpass(sig, cutoff, 2)
    env = ramp(t, [(0, 0), (0.04, 0.22), (0.15, 0.16), (dur - 0.08, 0.16), (dur, 0), (dur + 1, 0)])
    return sig * env


def echo(x, delay=0.18, fb=0.35, wet=0.35, tail=1.2):
    d = int(delay * SR)
    y = np.concatenate([x, np.zeros(int(tail * SR))])
    buf = np.zeros_like(y)
    for i in range(d, len(y)):
        buf[i] = y[i - d] + fb * buf[i - d]
    return y + wet * buf


def mix(events, length):
    out = np.zeros(int(length * SR))
    for at, sig in events:
        s = int(at * SR)
        e = min(len(out), s + len(sig))
        out[s:e] += sig[: e - s]
    return out


def fanfare():
    N = {"G4": 392, "C5": 523.25, "E5": 659.25, "G5": 783.99}
    seq = [("G4", 0, 0.16), ("C5", 0.18, 0.16), ("E5", 0.36, 0.16), ("G5", 0.54, 0.4), ("E5", 0.98, 0.16), ("G5", 1.16, 0.9)]
    return echo(mix([(at, brass(N[n], d)) for n, at, d in seq], 2.2))


def chime():
    events = []
    for i, f in enumerate([1318.5, 1568, 2093, 2637, 3136]):
        t = np.arange(int(1.3 * SR)) / SR
        env = np.where(t < 0.01, t / 0.01 * 0.12, 0.12 * np.exp(np.log(0.0001 / 0.12) * (t - 0.01) / 1.19))
        events.append((i * 0.09, np.sin(2 * np.pi * f * t) * env))
    return echo(mix(events, 1.8))


def write_wav(name, x):
    x = x / max(1e-9, np.max(np.abs(x))) * 0.89
    with wave.open(os.path.join(OUT, name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def main():
    os.makedirs(OUT, exist_ok=True)
    write_wav("fanfare.wav", fanfare())
    write_wav("chime.wav", chime())
    for name, text in VOICES.items():
        aiff = os.path.join(OUT, name + ".aiff")
        # [[pbas]] raises the pitch a little, like the web voice's pitch 1.25
        subprocess.run(["say", "-v", "Tingting", "-r", "190", "-o", aiff, "[[pbas 62]]" + text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", "-c", "1", aiff, os.path.join(OUT, name + ".wav")], check=True)
        os.remove(aiff)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
