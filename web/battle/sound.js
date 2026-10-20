// Battle score + SFX, synthesised with WebAudio (no files). Upgrade path: swap for recorded stems.
import { audioCtx } from '../audio.js';

let master, musicBus, sfxBus, noiseBuf;
function init() {
  const ctx = audioCtx(); if (!ctx || master) return ctx;
  master = ctx.createDynamicsCompressor(); master.threshold.value = -12; master.ratio.value = 4; master.connect(ctx.destination);
  musicBus = ctx.createGain(); musicBus.gain.value = 0.55; musicBus.connect(master);
  sfxBus = ctx.createGain(); sfxBus.gain.value = 0.9; sfxBus.connect(master);
  noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
  const d = noiseBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return ctx;
}
const now = () => audioCtx().currentTime;

function env(g, t, a, peak, hold, rel) {
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + a);
  g.gain.setValueAtTime(peak, t + a + hold); g.gain.exponentialRampToValueAtTime(0.0001, t + a + hold + rel);
}
function noise(t, dur, { type = 'lowpass', f0 = 1000, f1 = f0, q = 1, gain = 0.5, bus = sfxBus } = {}) {
  const ctx = audioCtx(), src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
  src.buffer = noiseBuf; f.type = type; f.Q.value = q;
  f.frequency.setValueAtTime(f0, t); f.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
  env(g, t, 0.01, gain, dur * 0.3, dur * 0.7);
  src.connect(f).connect(g).connect(bus); src.start(t); src.stop(t + dur + 0.1);
}
function tone(t, dur, { type = 'sine', f0 = 100, f1 = f0, gain = 0.5, a = 0.005, bus = sfxBus } = {}) {
  const ctx = audioCtx(), o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
  env(g, t, a, gain, 0, dur); o.connect(g).connect(bus); o.start(t); o.stop(t + dur + 0.1);
}

// ---------------- SFX ----------------
export const sfx = {
  step(big = 1) { if (!init()) return; const t = now(); tone(t, 0.35, { f0: 70 * (2 - big * 0.6), f1: 30, gain: 0.5 * big }); noise(t, 0.15, { f0: 400, f1: 80, gain: 0.25 * big }); },
  roar() { if (!init()) return; const t = now(); for (const m of [1, 1.5, 2.01]) tone(t, 1.6, { type: 'sawtooth', f0: 85 * m, f1: 60 * m, gain: 0.12, a: 0.15 }); noise(t, 1.6, { type: 'bandpass', f0: 500, f1: 250, q: 2, gain: 0.35 }); },
  whoosh(dur = 0.4, up = true) { if (!init()) return; const t = now(); noise(t, dur, { type: 'bandpass', f0: up ? 300 : 2500, f1: up ? 2500 : 300, q: 3, gain: 0.5 }); },
  wave() { if (!init()) return; const t = now(); noise(t, 1.2, { type: 'lowpass', f0: 3000, f1: 120, gain: 0.6 }); tone(t, 1.0, { type: 'sawtooth', f0: 220, f1: 40, gain: 0.18 }); },
  slash() { if (!init()) return; const t = now(); noise(t, 0.5, { type: 'highpass', f0: 6000, f1: 1200, gain: 0.5 }); tone(t, 0.6, { type: 'triangle', f0: 1800, f1: 300, gain: 0.15 }); },
  boom(size = 1) { if (!init()) return; const t = now(); tone(t, 1.4 * size, { f0: 90, f1: 25, gain: 0.9 }); noise(t, 1.0 * size, { f0: 1800, f1: 60, gain: 0.6 }); },
  ring() { if (!init()) return; const t = now(); for (const f of [880, 1320, 1760]) tone(t, 1.2, { type: 'sine', f0: f, f1: f * 0.98, gain: 0.08 }); },
  spin(i) { if (!init()) return; const t = now(); noise(t, 0.28, { type: 'bandpass', f0: 500 + i * 400, f1: 1600 + i * 600, q: 4, gain: 0.45 }); },
  impact() { if (!init()) return; const t = now(); tone(t, 1.8, { f0: 120, f1: 28, gain: 1 }); noise(t, 0.35, { type: 'highpass', f0: 4000, f1: 800, gain: 0.7 }); tone(t, 2.5, { type: 'sine', f0: 2093, f1: 2080, gain: 0.12 }); },
  thud() { if (!init()) return; const t = now(); tone(t, 2.0, { f0: 60, f1: 20, gain: 1 }); noise(t, 1.6, { f0: 900, f1: 50, gain: 0.7 }); },
};

// ---------------- music ----------------
// D minor battle ostinato + taiko-ish drums; intensity 0..1 thickens it. stop() for the hit, victory() after.
let timer = null, nextT = 0, step16 = 0, intensity = 0.3, bpm = 112;
const D = 146.83, scale = [1, 1, 1.189, 1, 1.335, 1, 1.498, 1.335];   // D D F D G D A G
function drum(t, big) { tone(t, 0.5, { f0: big ? 110 : 160, f1: 45, gain: big ? 0.7 : 0.35, bus: musicBus }); noise(t, 0.08, { f0: 900, f1: 200, gain: big ? 0.25 : 0.12, bus: musicBus }); }
function pluck(t, f, g) { tone(t, 0.22, { type: 'sawtooth', f0: f, f1: f * 0.995, gain: g, bus: musicBus }); }
function stab(t, fs, g) { for (const f of fs) tone(t, 0.45, { type: 'sawtooth', f0: f, f1: f, gain: g, a: 0.02, bus: musicBus }); }
function tick() {
  const ctx = audioCtx(); if (!ctx) return;
  const spb = 60 / bpm / 4;
  while (nextT < ctx.currentTime + 0.15) {
    const s = step16 % 16, bar = Math.floor(step16 / 16);
    if (s % 4 === 0 || (intensity > 0.6 && s % 4 === 2)) drum(nextT, s === 0 || s === 8);
    if (intensity > 0.4 && (s === 3 || s === 11)) drum(nextT, false);
    if (s % 2 === 0) pluck(nextT, D * scale[(s / 2) % 8] * (bar % 2 ? 1 : 1), 0.06 + 0.06 * intensity);
    if (intensity > 0.55 && s === 0) stab(nextT, bar % 2 ? [D, D * 1.189, D * 1.498] : [D * 0.891, D * 1.122, D * 1.335], 0.05 + 0.05 * intensity);
    if (intensity > 0.85 && s % 2 === 1) noise(nextT, 0.04, { type: 'highpass', f0: 7000, f1: 6000, gain: 0.08, bus: musicBus });
    nextT += spb; step16++;
  }
}
export const music = {
  start() { const ctx = init(); if (!ctx || timer) return; musicBus.gain.setValueAtTime(0.55, ctx.currentTime); nextT = ctx.currentTime + 0.05; step16 = 0; timer = setInterval(tick, 40); },
  set(i, tempo) { intensity = i; if (tempo) bpm = tempo; },
  stop(fade = 0.05) { const ctx = audioCtx(); if (!ctx || !musicBus) return; musicBus.gain.setTargetAtTime(0.0001, ctx.currentTime, fade); clearInterval(timer); timer = null; },
  victory() {
    const ctx = init(); if (!ctx) return; musicBus.gain.setValueAtTime(0.6, ctx.currentTime);
    const t = ctx.currentTime + 0.05, F = { D4: 293.7, F4: 349.2, A4: 440, D5: 587.3, E5: 659.3, Fs5: 740, A5: 880 };
    const seq = [['D4', 0, 0.2], ['A4', 0.22, 0.2], ['D5', 0.44, 0.2], ['Fs5', 0.66, 0.5], ['E5', 1.2, 0.2], ['Fs5', 1.42, 0.2], ['A5', 1.64, 1.4]];
    for (const [n, at, d] of seq) { stab(t + at, [F[n], F[n] * 1.5], 0.09); drum(t + at, at === 0 || at > 1.6); }
  },
};
