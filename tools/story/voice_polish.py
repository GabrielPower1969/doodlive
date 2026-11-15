#!/usr/bin/env python3
"""Post-pass for a pack's voice clips (any engine), idempotent:  python3 tools/story/voice_polish.py <id> [--lang zh|en] [--dry]

  1. Leading / trailing digital silence longer than 0.25 s is cut back to the house pad (0.03 s in, 0.06 s out).
  2. Mid-line digital dropouts (stretches under -70 dBFS, 60 ms or longer, between speech) are filled with a very quiet
     room tone (-74 dBFS, low-passed noise, 8 ms crossfades): a hard digital zero in the middle of a line is heard as
     the sound "dropping out" on headphones (review 2026-11-15, Joseph js_13).
  3. A silence stretch longer than 0.8 s inside a line is cut to 0.8 s (a TTS model sometimes dead-airs).
  4. Level re-checked: -16 LUFS +-1 and true peak <= -1.5 dBTP, else a plain gain fix; the MP3 is re-encoded.
Run `python3 tools/story/voice.py <id> check` afterwards (durations.json, report.json, srt).
"""
import argparse, glob, os, subprocess, sys
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import voice as V  # noqa: E402

FLOOR = 10 ** (-70 / 20)
TONE = 10 ** (-74 / 20)


def runs(mask, sr, min_s):
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if (j - i) / sr >= min_s:
                out.append((i, j))
            i = j
        else:
            i += 1
    return out


def _quiet(x, sr):
    """Samples inside a stretch whose 10 ms RMS is under -64 dBFS (digital zero, or an earlier room-tone fill)."""
    h = int(0.01 * sr)
    n = len(x) // h
    rms = np.sqrt(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1))
    q = np.repeat(rms < 10 ** (-64 / 20), h)
    return np.concatenate([q, np.full(len(x) - len(q), q[-1] if len(q) else True)])


def polish(x, sr, seed=3):
    notes = []
    quiet = np.abs(x) < FLOOR
    loud = np.where(~quiet)[0]
    if not len(loud):
        return x, notes
    a, b = loud[0], loud[-1] + 1
    lead, tail = a / sr, (len(x) - b) / sr
    start, end = 0, len(x)
    if lead > 0.25:
        start = max(0, a - int(0.03 * sr)); notes.append(f"lead {lead:.2f}s cut")
    if tail > 0.25:
        end = min(len(x), b + int(0.06 * sr)); notes.append(f"tail {tail:.2f}s cut")
    x = x[start:end].copy()
    quiet = _quiet(x, sr)
    rng = np.random.default_rng(seed)
    noise = sosfilt(butter(2, 3000, "low", fs=sr, output="sos"), rng.standard_normal(len(x)))
    noise = (noise / (np.std(noise) + 1e-9) * TONE).astype(np.float32)
    keep = np.ones(len(x), bool)
    filled = 0
    for i, j in runs(quiet, sr, 0.06):
        if i < int(0.04 * sr) or j > len(x) - int(0.04 * sr):
            continue                                         # the pads at the clip ends stay silent
        f = int(0.008 * sr)
        seg = noise[i:j].copy()
        seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        x[i:j] = seg                                          # replaces zeros or an earlier fill: idempotent
        filled += 1
        if (j - i) / sr > 0.8:                               # dead air: keep 0.8 s
            cut = (j - i) - int(0.8 * sr)
            keep[i + int(0.4 * sr): i + int(0.4 * sr) + cut] = False
            notes.append(f"{(j - i) / sr:.2f}s pause cut to 0.8s")
    if not keep.all():
        x = x[keep]
    if filled:
        notes.append(f"{filled} dropout(s) filled with room tone")
    return x, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story"); ap.add_argument("--lang", default="all"); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    d = os.path.join(V.ROOT, "assets", a.story, "audio", "voice")
    only = set(a.only.split(",")) if a.only else None
    for lang in (V.LANGS if a.lang == "all" else (a.lang,)):
        for f in sorted(glob.glob(os.path.join(d, lang, "*.wav"))):
            lid = os.path.basename(f)[:-4]
            if only and lid not in only:
                continue
            x, sr = sf.read(f, dtype="float32")
            y, notes = polish(x, sr)
            lu0, pk0 = V.loudness(f)
            if not notes:
                if abs(lu0 + 16) > 1.0 or pk0 > -1.5:
                    print(f"{lang} {lid}: LEVEL {lu0:.1f} LUFS {pk0:.1f} dBTP (not touched, no edit)")
                continue
            print(f"{lang} {lid}: {', '.join(notes)}")
            if a.dry:
                continue
            tmp = f + ".polish.wav"
            sf.write(tmp, y, sr, subtype="PCM_16")
            lu, pk = V.loudness(tmp)
            if abs(lu + 16) > 0.5 or pk > -1.5:
                g = -16 - lu
                V.ffmpeg("-i", tmp, "-af", f"volume={g:.2f}dB,alimiter=limit={10 ** ((V.TP - 0.6) / 20):.3f}:attack=8:release=200:level=disabled",
                         "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", tmp + ".g.wav")
                os.replace(tmp + ".g.wav", tmp)
                lu, pk = V.loudness(tmp)
                print(f"   level fixed: {lu:.2f} LUFS {pk:.2f} dBTP")
            os.replace(tmp, f)
            V.ffmpeg("-i", f, "-ac", "1", "-b:a", "96k", f[:-4] + ".mp3")


if __name__ == "__main__":
    main()
