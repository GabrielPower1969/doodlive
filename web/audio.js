// Sound: synthesised trumpet fanfare + sparkle chime (WebAudio) and a TTS voice (Web Speech).
// Upgrade path: drop recorded files into web/assets/sfx/ and play them instead.
let ctx;
export function unlockAudio() {
  ctx ||= new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === 'suspended') ctx.resume();
  // Chrome on Android only loads voices after a first call
  try { speechSynthesis.getVoices(); } catch { /* no TTS */ }
}

function reverbBus() {
  const delay = ctx.createDelay(); delay.delayTime.value = 0.18;
  const fb = ctx.createGain(); fb.gain.value = 0.35;
  const wet = ctx.createGain(); wet.gain.value = 0.35;
  delay.connect(fb).connect(delay); delay.connect(wet).connect(ctx.destination);
  return delay;
}

function brass(freq, start, dur, out) {
  const g = ctx.createGain(), lp = ctx.createBiquadFilter();
  lp.type = 'lowpass'; lp.Q.value = 2;
  lp.frequency.setValueAtTime(600, start);
  lp.frequency.linearRampToValueAtTime(3200, start + 0.06);
  lp.frequency.linearRampToValueAtTime(2000, start + dur);
  g.gain.setValueAtTime(0, start);
  g.gain.linearRampToValueAtTime(0.22, start + 0.04);
  g.gain.linearRampToValueAtTime(0.16, start + 0.15);
  g.gain.setValueAtTime(0.16, start + dur - 0.08);
  g.gain.linearRampToValueAtTime(0, start + dur);
  const vib = ctx.createOscillator(), vg = ctx.createGain();
  vib.frequency.value = 5.5; vg.gain.value = freq * 0.006;
  vib.connect(vg);
  for (const [type, mul, gain] of [['sawtooth', 1, 1], ['square', 1.002, 0.4], ['sawtooth', 2, 0.25]]) {
    const o = ctx.createOscillator(), og = ctx.createGain();
    o.type = type; o.frequency.value = freq * mul; og.gain.value = gain;
    vg.connect(o.frequency);
    o.connect(og).connect(lp);
    o.start(start); o.stop(start + dur + 0.05);
  }
  vib.start(start); vib.stop(start + dur + 0.05);
  lp.connect(g); g.connect(ctx.destination); g.connect(out);
}

export function fanfare() {
  if (!ctx) return 0;
  const t = ctx.currentTime + 0.05, rv = reverbBus();
  const N = { G4: 392, C5: 523.25, E5: 659.25, G5: 783.99, C6: 1046.5 };
  const seq = [['G4', 0, 0.16], ['C5', 0.18, 0.16], ['E5', 0.36, 0.16], ['G5', 0.54, 0.4], ['E5', 0.98, 0.16], ['G5', 1.16, 0.9]];
  seq.forEach(([n, at, d]) => brass(N[n], t + at, d, rv));
  return 2.1;
}

export function chime() {
  if (!ctx) return;
  const t = ctx.currentTime + 0.02, rv = reverbBus();
  [1318.5, 1568, 2093, 2637, 3136].forEach((f, i) => {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'sine'; o.frequency.value = f;
    const s = t + i * 0.09;
    g.gain.setValueAtTime(0, s); g.gain.linearRampToValueAtTime(0.12, s + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, s + 1.2);
    o.connect(g); g.connect(ctx.destination); g.connect(rv);
    o.start(s); o.stop(s + 1.3);
  });
}

export function say(text) {
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const voices = speechSynthesis.getVoices();
    const zh = voices.find(v => /zh[-_]CN/i.test(v.lang)) || voices.find(v => /^zh/i.test(v.lang));
    if (zh) u.voice = zh;
    u.lang = zh?.lang || 'zh-CN'; u.rate = 0.95; u.pitch = 1.25;
    speechSynthesis.speak(u);
  } catch { /* no TTS on this device */ }
}
