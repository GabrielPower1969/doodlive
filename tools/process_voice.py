#!/usr/bin/env python3
"""Turn the raw takes from web/record.html (NN_T.wav) into the app's voice clips.

Per line: pick a take (default = loudest non-clipped take, override with --pick 03=2), trim silence, high-pass,
gentle de-noise, compress, normalise to -16 LUFS, add a touch of room ("halo") and export:
  web/assets/voice/<set>/<name>.mp3   unity/Assets/DoodLive/Audio/<name>.wav
Also writes every processed take to <out>/review/ so the choice can be auditioned.
Usage: python3 tools/process_voice.py RAW_DIR [--set gabriel] [--pick 01=2 --pick 06=3] [--dry]
"""
import argparse, glob, json, os, re, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = {"01": "voice_hello", "02": "voice_0", "03": "voice_1", "04": "voice_2", "05": "voice_3",
         "06": "laugh", "07": "wow", "08": "hum", "09": "fly", "10": "narrator"}

def stats(f):
    out = subprocess.run(["ffmpeg", "-i", f, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    mean = float(re.search(r"mean_volume: ([-\d.]+)", out).group(1)); peak = float(re.search(r"max_volume: ([-\d.]+)", out).group(1))
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
    return mean, peak, dur

def chain(dry):
    f = ["silenceremove=start_periods=1:start_threshold=-38dB:start_silence=0.15",
         "areverse", "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.35", "areverse",
         "highpass=f=80", "afftdn=nf=-32:nr=10", "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2",
         "loudnorm=I=-16:TP=-1.5:LRA=9"]
    if not dry: f.append("aecho=0.75:0.22:28|53:0.14|0.09")     # small bright room, keeps intelligibility
    return ",".join(f)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("--set", default="gabriel"); ap.add_argument("--pick", action="append", default=[]); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    picks = dict(p.split("=") for p in a.pick)
    web, unity, review = f"{ROOT}/web/assets/voice/{a.set}", f"{ROOT}/unity/Assets/DoodLive/Audio", f"{a.raw}/review"
    for d in (web, unity, review): os.makedirs(d, exist_ok=True)
    report = {}
    for line, name in NAMES.items():
        takes = sorted(glob.glob(f"{a.raw}/{line}_*.wav"))
        if not takes: print(f"{line} {name}: no takes"); continue
        info = {t: stats(t) for t in takes}
        for t in takes:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", t, "-af", chain(a.dry), "-ac", "1", "-ar", "44100", f"{review}/{os.path.basename(t)}"], check=True)
        if line in picks: best = f"{a.raw}/{line}_{picks[line]}.wav"
        else:
            ok = [t for t in takes if info[t][1] < -1.0] or takes            # avoid clipped takes
            best = max(ok, key=lambda t: info[t][0])                          # loudest = most committed delivery
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", best, "-af", chain(a.dry), "-ac", "1", "-ar", "44100", f"{unity}/{name}.wav"], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{unity}/{name}.wav", "-b:a", "96k", f"{web}/{name}.mp3"], check=True)
        d = stats(f"{unity}/{name}.wav")[2]
        report[name] = {"take": os.path.basename(best), "seconds": round(d, 2), "candidates": {os.path.basename(t): [round(v, 1) for v in info[t]] for t in takes}}
        print(f"{line} {name:12s} <- {os.path.basename(best)}  {d:4.1f}s   (mean/peak/dur per take: {report[name]['candidates']})")
    json.dump(report, open(f"{web}/picks.json", "w"), indent=1, ensure_ascii=False)

if __name__ == "__main__": main()
