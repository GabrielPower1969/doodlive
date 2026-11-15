#!/usr/bin/env python3
"""voice_margin: how far the voice sits over everything else, line by line, as the app will actually mix it.

  python3 tools/story/voice_margin.py <id> [--lang zh] [--quiet] [--wav out.wav]

Models unity/Assets/DoodLive/Story/StoryDirector.cs (read it again if the engine changes):
  * every line plays at volume 1 at its (re-timed) start, for the length of its clip;
  * music = cue file x 0.8 x duck, duck 1 -> 0.5 at 2.5 / s while a voice clip plays (so music is -8 dB under speech);
    a cue plays from its start, jumps back (loopEnd - loopStart) at loopEnd, fades out 0.6 s when the next cue starts;
  * SFX one-shots and the SFX loop are NOT ducked: they play at mix.json gainDb. The loop has no fade-in (fadeInSec is
    ignored by the engine) and fades out linearly when its stopAtCue starts.
Timing = the timeline re-timed to the clips of --lang (what the phone plays), built by tools/story/build_timeline.py.

Per line: voice level (RMS over its active frames, 100 Hz - 6 kHz) against the bed (music + SFX, same frames and band),
in dB. "vs music" / "vs sfx" give each part's own margin. This is an engine-model number, not the reviewer's
cross-correlation residual (which has a codec floor); compare packs with each other (Daniel = the reference).
"""
import argparse, json, os, sys, wave
import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
SR = 44100


def clip_secs(path):
    with wave.open(path) as w: return w.getnframes() / w.getframerate()


def lang_timeline(sid, lang="zh"):
    """The timeline as the app plays it in `lang` (re-timed to the installed clips)."""
    import build_timeline as bt
    vd = f"{ROOT}/assets/{sid}/audio/voice/{lang}"
    base = json.load(open(f"{ROOT}/assets/{sid}/timeline.json"))
    if os.path.exists(f"{ROOT}/docs/{sid}/storyboard/story.py"):
        d = {l["id"]: clip_secs(f"{vd}/{l['id']}.wav") for l in base["lines"] if os.path.exists(f"{vd}/{l['id']}.wav")}
        other = "en" if lang == "zh" else "zh"
        tl = bt.build(sid, write=False, durations={lang: d, other: {}})
    else:
        tl = base
    for l in tl["lines"]:
        p = f"{vd}/{l['id']}.wav"
        l["clip"] = clip_secs(p) if os.path.exists(p) else l.get("dur", 3)
    return tl


def load(path):
    sr, x = wavfile.read(path); x = x.astype(np.float64) / 32768.0
    assert sr == SR; return x if x.ndim == 1 else x.mean(1)


def engine_mix(sid, tl, lang="zh", music_dir=None, sfx_dir=None):
    """-> dict(voice, music, sfx, n): float arrays at SR. Engine model, see the module docstring."""
    A = f"{ROOT}/assets/{sid}/audio"; music_dir = music_dir or f"{A}/music"; sfx_dir = sfx_dir or f"{A}/sfx"
    n = int((tl["duration"] + 3.0) * SR)
    voice = np.zeros(n); music = np.zeros(n); sfx = np.zeros(n); duck_on = np.zeros(n, bool)
    for l in tl["lines"]:
        i = int(round(l["t"] * SR)); x = load(f"{A}/voice/{lang}/{l['id']}.wav"); m = min(len(x), n - i)
        voice[i:i + m] += x[:m]; duck_on[i:i + m] = True
    step = 2.5 / 60.0; duck = np.empty(n); cur = 1.0; fr = SR // 60          # MoveTowards(duck, playing ? .5 : 1, dt * 2.5)
    for i in range(0, n, fr):
        cur = cur + np.clip((0.5 if duck_on[i] else 1.0) - cur, -step, step); duck[i:i + fr] = cur
    cues = json.load(open(f"{music_dir}/cues.json"))["cues"]; byname = {}
    for c in cues: byname.setdefault(c["cue"], c)
    seq = sorted(tl["music"], key=lambda c: c["t"])
    for k, c in enumerate(seq):
        t0 = c["t"]; t1 = seq[k + 1]["t"] if k + 1 < len(seq) else tl["duration"] + 3.0
        x = load(f"{music_dir}/{c['cue']}.wav"); e = byname[c["cue"]]; ls, le = e["loopStartSample"], e["loopEndSample"]
        i0 = int(round(t0 * SR)); i1 = min(n, int(round((t1 + 0.6) * SR)))
        idx = np.arange(i1 - i0); idx = np.where(idx >= le, ls + (idx - ls) % (le - ls), idx)
        out = x[np.minimum(idx, len(x) - 1)] * (idx < len(x))
        g = 0.8 * duck[i0:i1]
        if k + 1 < len(seq):                       # old cue: volume frozen at the switch, linear to 0 over 0.6 s
            f0 = int(round((t1 - t0) * SR)); fl = int(0.6 * SR); frozen = g[min(f0, len(g) - 1)]
            seg = g[f0:f0 + fl]; g[f0:f0 + fl] = frozen * np.linspace(1, 0, fl)[:len(seg)]
        music[i0:i1] += out * g
    mx = {m["id"]: m for m in json.load(open(f"{sfx_dir}/mix.json"))["sfx"]}
    for s in tl["sfx"]:
        m = mx[s["id"]]; x = load(f"{sfx_dir}/{s['id']}.wav"); gain = 10 ** (m["gainDb"] / 20); i0 = int(round(s["t"] * SR))
        if m.get("loop"):
            stop = [c["t"] for c in seq if c["cue"] == m.get("stopAtCue") and c["t"] > s["t"] + 1.0]
            t_end = stop[0] if stop else tl["duration"]; fade = m.get("fadeOutSec", 1.0)
            ln = int((t_end - s["t"] + fade) * SR); y = np.tile(x, ln // len(x) + 1)[:ln] * gain
            fi = int((t_end - s["t"]) * SR); y[fi:] *= np.linspace(1, 0, len(y) - fi)
        else:
            y = x * gain
        m_ = min(len(y), n - i0); sfx[i0:i0 + m_] += y[:m_]
    return dict(voice=voice, music=music, sfx=sfx, n=n)


def band(x):
    return signal.sosfilt(signal.butter(2, [100, 6000], "bandpass", fs=SR, output="sos"), x)


def table(tl, mix):
    v, m, s = band(mix["voice"]), band(mix["music"]), band(mix["sfx"]); hop = int(.05 * SR); rows = []
    fr = lambda a, i0, nf: np.array([np.mean(a[i0 + k * hop:i0 + (k + 1) * hop] ** 2) for k in range(nf)])
    db = lambda a, b: 10 * np.log10(a / max(b, 1e-14))
    for l in tl["lines"]:
        i0 = int(round(l["t"] * SR)); nf = int(l["clip"] * SR) // hop
        fv, fm, fs = fr(v, i0, nf), fr(m, i0, nf), fr(s, i0, nf)
        act = fv > fv.max() * 10 ** (-3.0)
        pv, pm, ps = fv[act].mean(), fm[act].mean(), fs[act].mean()
        rows.append(dict(id=l["id"], who=l["who"], t=l["t"], vs_bed=db(pv, pm + ps), vs_mus=db(pv, pm), vs_sfx=db(pv, ps)))
    return rows


def show(rows, title=""):
    print(f"{title}\n id     who        t(s)  voice-vs-bed  vs music  vs sfx")
    for r in rows:
        print(f" {r['id']:6s} {r['who']:9s} {r['t']:6.1f}  {r['vs_bed']:8.1f} dB  {r['vs_mus']:6.1f}  {r['vs_sfx']:6.1f}")
    return summary(rows, True)


def summary(rows, echo=False):
    a = np.array([r["vs_bed"] for r in rows]); w = sorted(rows, key=lambda r: r["vs_bed"])[:3]
    if echo: print(f" median {np.median(a):.1f} dB, mean {a.mean():.1f}, worst 3: " + ", ".join(f"{r['id']} {r['vs_bed']:.1f}" for r in w))
    return float(np.median(a)), [(r["id"], round(r["vs_bed"], 1)) for r in w]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("id"); ap.add_argument("--lang", default="zh")
    ap.add_argument("--wav"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    tl = lang_timeline(a.id, a.lang); mix = engine_mix(a.id, tl, a.lang); rows = table(tl, mix)
    if a.quiet:
        med, worst = summary(rows); print(a.id, f"median {med:.1f}", worst)
    else:
        show(rows, f"{a.id} ({a.lang}, {tl['duration']:.1f} s)")
    if a.wav:
        o = mix["voice"] + mix["music"] + mix["sfx"]; wavfile.write(a.wav, SR, (np.clip(o, -1, 1) * 32767).astype(np.int16))
