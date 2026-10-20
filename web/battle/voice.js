// Recorded voice lines (web/assets/voice/<lang>/<who>.mp3, made by tools/make_voice.sh) with the
// same queued contract as audio.js say(): lines never interrupt each other; onstart/onend bracket
// each line. Falls back to Web Speech when a clip is missing or blocked (LESSONS L20).
import { say } from '../audio.js';

const clips = new Map();
let chain = Promise.resolve();

export function preloadVoice(lang, names) {
  for (const n of names) {
    const a = new Audio(`assets/voice/${lang}/${n}.mp3`);
    a.preload = 'auto';
    clips.set(`${lang}/${n}`, a);
  }
}

/** Queue one line. `text` is the spoken text, used only by the TTS fallback. */
export function voice(lang, name, text, { onstart, onend, fallback = {} } = {}) {
  chain = chain.then(() => new Promise(resolve => {
    const done = () => { onend?.(); resolve(); };
    const a = clips.get(`${lang}/${name}`);
    const tts = () => say(text, { ...fallback, lang, queue: true, onstart, onend: done });
    if (!a) return tts();
    let started = false;
    a.currentTime = 0;
    a.onplaying = () => { if (!started) { started = true; onstart?.(); } };
    a.onended = done;
    a.onerror = () => { if (!started) tts(); else done(); };
    a.play().catch(() => tts());   // autoplay policy or missing file → Web Speech
  }));
  return chain;
}

export function stopVoice() {
  for (const a of clips.values()) { try { a.pause(); a.currentTime = 0; } catch { /* not started */ } }
  chain = Promise.resolve();
  try { speechSynthesis.cancel(); } catch { /* no TTS */ }
}
