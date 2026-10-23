// DoodLive prototype: scan -> bake texture -> angel enters -> tap = trumpet + voice.
// Three ways to show her:
//   xr    WebXR immersive-ar (ARCore): world-locked on a real surface, gravity-up. Best; Chrome on ARCore phones.
//   paper camera feed + marker tracking; upright via the gravity sensor, rises out of the page.
//   show  turntable over a dark backdrop (no camera / demo).
import * as THREE from 'three';
import { buildAngel, animate, radialTexture } from './angel.js';
import { loadAngelGLB } from './angel_glb.js';
import { buildFx } from './fx.js';
import { homography, detectMarkers, warpArt, whiteBalance, eraseLines, poseFromH } from './vision.js';
import { unlockAudio, fanfare, chime, say, audioCtx } from './audio.js';
import { t, other, lang, setLang, apply as applyLang } from './i18n.js';

const $ = id => document.getElementById(id);
const video = $('video'), glCanvas = $('gl');
const tpl = await (await fetch('assets/template.json')).json();
const build = await fetch('build.json').then(r => r.json()).catch(() => ({ sha: 'dev', time: '' }));
console.log(`DoodLive web build ${build.sha}.${build.time}`);
const TEX = 1024;
const [AX, AY, AWT, AHT] = tpl.art;   // art rectangle on the sheet, template px

// ---------------- three.js ----------------
const renderer = new THREE.WebGLRenderer({ canvas: glCanvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.xr.enabled = true;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, 1, 10, 1e5);   // px units outside XR, metres inside
scene.add(new THREE.HemisphereLight(0xfff6e8, 0x6070a0, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(0.4, 1, 0.8); scene.add(sun);
const fill = new THREE.DirectionalLight(0xbfd4ff, 0.6); fill.position.set(-1, 0.2, 0.5); scene.add(fill);

const canvasTex = document.createElement('canvas'); canvasTex.width = canvasTex.height = TEX;
const texture = new THREE.CanvasTexture(canvasTex);
texture.colorSpace = THREE.SRGBColorSpace; texture.anisotropy = 4;
const angel = await loadAngelGLB(texture).catch(e => { console.warn('GLB angel failed, using the code-built one', e); return buildAngel(texture); });
angel.root.visible = false;
const fx = buildFx(angel.root);

const blob = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.6), new THREE.MeshBasicMaterial({ map: radialTexture('rgba(20,20,40,0.55)'), transparent: true, depthWrite: false }));
blob.rotation.x = -Math.PI / 2; blob.position.y = 0.002; angel.root.add(blob);
const SPARK = 220, sparkPos = new Float32Array(SPARK * 3), sparkSeed = new Float32Array(SPARK);
for (let i = 0; i < SPARK; i++) sparkSeed[i] = Math.random();
const sparkGeom = new THREE.BufferGeometry(); sparkGeom.setAttribute('position', new THREE.BufferAttribute(sparkPos, 3));
const sparks = new THREE.Points(sparkGeom, new THREE.PointsMaterial({ map: radialTexture('rgba(255,245,200,1)'), size: 0.04, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
angel.root.add(sparks);

// holders: paper (matrix computed each frame), show (turntable), xr (world-locked)
const paperHolder = new THREE.Group(); paperHolder.matrixAutoUpdate = false; scene.add(paperHolder);
const showHolder = new THREE.Group(); scene.add(showHolder);
showHolder.position.set(0, -720, -2700); showHolder.scale.setScalar(1250);
const xrHolder = new THREE.Group(); scene.add(xrHolder); xrHolder.scale.setScalar(0.26);   // ≈32 cm tall
const reticle = new THREE.Mesh(new THREE.RingGeometry(0.06, 0.08, 40).rotateX(-Math.PI / 2),
  new THREE.MeshBasicMaterial({ color: 0xffe08a, transparent: true, opacity: 0.9 }));
reticle.matrixAutoUpdate = false; reticle.visible = false; scene.add(reticle);

// ---------------- state ----------------
const S = { mode: 'start', view: 'show', lines: false, phase: 'idle', phaseT: 0, good: 0, lastPts: null, lost: 0,
  rawTex: null, cleanTex: null, voiceIdx: 0, havePose: false, xr: null, xrPlaced: false, hasGrav: false };
const targetPose = { p: new THREE.Vector3(), q: new THREE.Quaternion() };
const curPose = { p: new THREE.Vector3(), q: new THREE.Quaternion() };
const FLIP = new THREE.Matrix4().makeScale(1, -1, -1);
const grav = new THREE.Vector3(0, 1, 0);   // "up" in camera coords, from the accelerometer

addEventListener('devicemotion', e => {
  const a = e.accelerationIncludingGravity;
  if (!a || a.x == null) return;
  const v = new THREE.Vector3(a.x, a.y, a.z);
  if (v.lengthSq() < 1) return;
  const ang = THREE.MathUtils.degToRad(screen.orientation?.angle || 0);
  v.applyAxisAngle(new THREE.Vector3(0, 0, 1), -ang).normalize();
  grav.lerp(v, S.hasGrav ? 0.15 : 1).normalize(); S.hasGrav = true;
});

let view = { sw: innerWidth, sh: innerHeight, scale: 1, ox: 0, oy: 0, f: 1000 };
function layout() {
  if (renderer.xr.isPresenting) return;
  view.sw = innerWidth; view.sh = innerHeight;
  renderer.setSize(view.sw, view.sh, false);
  const vw = video.videoWidth || 1080, vh = video.videoHeight || 1920;
  view.scale = Math.max(view.sw / vw, view.sh / vh);
  view.ox = (view.sw - vw * view.scale) / 2; view.oy = (view.sh - vh * view.scale) / 2;
  view.f = 0.8 * Math.max(vw, vh) * view.scale;            // ~65° on the long side; good enough for a phone
  camera.aspect = view.sw / view.sh;
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(view.sh / 2 / view.f));
  camera.updateProjectionMatrix();
  drawGuide();
}
addEventListener('resize', layout);

function guideQuad() {
  const [mx0, my0] = tpl.markers[0], [mx1, my1] = tpl.markers[2];
  const asp = (mx1 - mx0) / (my1 - my0);
  let w = view.sw * 0.84, h = w / asp;
  if (h > view.sh * 0.68) { h = view.sh * 0.68; w = h * asp; }
  const x = (view.sw - w) / 2, y = (view.sh - h) / 2 - view.sh * 0.03;
  return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
}
function drawGuide(pts) {
  const q = guideQuad();
  $('guide').setAttribute('viewBox', `0 0 ${view.sw} ${view.sh}`);
  $('guideQuad').setAttribute('points', q.map(p => p.join(',')).join(' '));
  $('corners').innerHTML = (pts || []).map(([x, y]) => `<circle cx="${x}" cy="${y}" r="9"/>`).join('');
  $('guide').classList.toggle('ok', !!pts);
}
const toVideo = ([x, y]) => [(x - view.ox) / view.scale, (y - view.oy) / view.scale];
const toScreen = ([x, y]) => [x * view.scale + view.ox, y * view.scale + view.oy];

// ---------------- camera + detection ----------------
const small = document.createElement('canvas'), sctx = small.getContext('2d', { willReadFrequently: true });
async function startCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: false,
    video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } } });
  video.srcObject = stream;
  await video.play();
  await new Promise(r => (video.videoWidth ? r() : video.addEventListener('loadedmetadata', r, { once: true })));
  layout();
}
function stopCamera() {
  video.srcObject?.getTracks().forEach(t => t.stop());
  video.srcObject = null;
}

function detect() {
  if (!video.videoWidth) return null;
  const k = 480 / Math.max(video.videoWidth, video.videoHeight);
  small.width = Math.round(video.videoWidth * k); small.height = Math.round(video.videoHeight * k);
  sctx.drawImage(video, 0, 0, small.width, small.height);
  const img = sctx.getImageData(0, 0, small.width, small.height);
  const expectedV = S.lastPts || guideQuad().map(toVideo);
  const g = guideQuad();
  const radius = Math.max(14, ((g[1][0] - g[0][0]) / view.scale) * k * (S.lastPts ? 0.16 : 0.2));
  const found = detectMarkers(img, expectedV.map(([x, y]) => [x * k, y * k]), radius);
  return found && found.map(([x, y]) => [x / k, y / k]);
}

function updatePose(ptsV) {
  const Hs = homography(tpl.markers, ptsV.map(toScreen));
  if (!Hs) return;
  const m = new THREE.Matrix4().fromArray(poseFromH(Hs, view.f, view.sw / 2, view.sh / 2)).premultiply(FLIP);
  m.decompose(targetPose.p, targetPose.q, new THREE.Vector3());
  if (!S.havePose) { curPose.p.copy(targetPose.p); curPose.q.copy(targetPose.q); S.havePose = true; }
}

// Paper mode placement: feet on the page, "up" = gravity (not the paper normal), facing the viewer.
// Flat sheet -> she stands on it (smaller, middle of the page). Upright sheet (wall/monitor) -> she
// overlays her own drawing at full size and leans out of it.
const _n = new THREE.Vector3(), _d = new THREE.Vector3(), _F = new THREE.Vector3(), _R = new THREE.Vector3(), _P = new THREE.Vector3();
function placeOnPaper() {
  const anchorM = new THREE.Matrix4().compose(curPose.p, curPose.q, new THREE.Vector3(1, 1, 1));
  _n.set(0, 0, -1).applyQuaternion(curPose.q);          // out of the paper, towards the camera
  _d.set(0, 1, 0).applyQuaternion(curPose.q);           // towards the bottom edge of the page
  const U = S.hasGrav ? grav : _n;
  const flat = THREE.MathUtils.smoothstep(Math.abs(_n.dot(U)), 0.45, 0.85);   // 1 = sheet lying flat
  _F.copy(_n).addScaledVector(U, -_n.dot(U));
  if (_F.lengthSq() < 0.09) _F.copy(_d).addScaledVector(U, -_d.dot(U));
  _F.normalize();
  _R.crossVectors(U, _F).normalize();
  const py = THREE.MathUtils.lerp(AY + AHT, AY + AHT * 0.66, flat);
  _P.set(AX + AWT / 2, py, 0).applyMatrix4(anchorM).addScaledVector(_n, AWT * 0.04 * (1 - flat));
  const s = AWT * THREE.MathUtils.lerp(1.0, 0.75, flat);
  paperHolder.matrix.makeBasis(_R.clone().multiplyScalar(s), U.clone().multiplyScalar(s), _F.clone().multiplyScalar(s)).setPosition(_P);
  paperHolder.matrixWorldNeedsUpdate = true;
}

// ---------------- capture / bake ----------------
function bakeFromCamera(ptsV) {
  const c = document.createElement('canvas'); c.width = video.videoWidth; c.height = video.videoHeight;
  const cx = c.getContext('2d', { willReadFrequently: true }); cx.drawImage(video, 0, 0);
  const frame = cx.getImageData(0, 0, c.width, c.height);
  const refined = detectMarkers(frame, ptsV, Math.max(24, c.width * 0.03)) || ptsV;
  const H = homography(tpl.markers, refined);
  setTextureData(whiteBalance(warpArt(frame, H, tpl, TEX)));
  return refined;
}
function setTextureData(img) { S.rawTex = img; S.cleanTex = eraseLines(img); paintTexture(); }
function paintTexture() {
  $('btnLines').textContent = t(S.lines ? 'linesOn' : 'linesOff');
  if (!S.rawTex) return;
  canvasTex.getContext('2d').putImageData(S.lines ? S.rawTex : S.cleanTex, 0, 0);
  texture.needsUpdate = true;
  $('btnLines').textContent = t(S.lines ? 'linesOn' : 'linesOff');
}
async function loadDemoTexture() {
  const img = new Image(); img.src = 'assets/demo-colored.png'; await img.decode();
  const c = document.createElement('canvas'); c.width = c.height = TEX;
  const x = c.getContext('2d'); x.drawImage(img, 0, 0, TEX, TEX);
  setTextureData(x.getImageData(0, 0, TEX, TEX));
}

// ---------------- flow ----------------
const status = t => { $('status').textContent = t; };
const show = (id, on) => $(id).classList.toggle('hidden', !on);
const setPhase = p => { S.phase = p; S.phaseT = 0; };
let xrSupported = false;
navigator.xr?.isSessionSupported('immersive-ar').then(v => { xrSupported = v; refreshButtons(); }).catch(() => {});

function refreshButtons() {
  const live = S.mode === 'live';
  show('btnShoot', S.mode === 'scan');
  show('btnNew', live && !S.xr); show('btnGate', live);
  show('btnLines', live); show('btnTitle', live && !!angel.title);
  show('btnMode', live && !S.xr && !!video.srcObject);
  show('btnXR', live && !S.xr && xrSupported);
  show('btnExitXR', !!S.xr);
  $('btnMode').textContent = t(S.view === 'paper' ? 'modeShow' : 'modePaper');
  document.body.classList.toggle('live', live && !S.xr);
  if (!live) { $('more').classList.remove('show'); show('hint', false); }
  for (const sp of $('langHud').querySelectorAll('span')) sp.classList.toggle('on', sp.dataset.l === lang);
}

// Recorded lines (Gabriel's own voice, zh and en sets) with Web Speech as the fallback; voices never overlap.
const VOICE_FILE = { hello: 'voice_hello', line0: 'voice_0', line1: 'voice_1', line2: 'voice_2', line3: 'voice_3', greet0: 'greet0', greet1: 'greet1', greet2: 'greet2' };
let currentClip = null;
const theme = new Audio('assets/music/theme.mp3'); theme.loop = true; const MUSIC_BED = 0.22;
function duck(on) { const target = on ? MUSIC_BED * 0.4 : MUSIC_BED; const step = () => { theme.volume += Math.sign(target - theme.volume) * 0.02; if (Math.abs(theme.volume - target) > 0.021) requestAnimationFrame(step); else theme.volume = target; }; step(); }
function subtitle(key) {
  const el = $('sub'); if (!key) { el.classList.remove('show'); return; }
  el.innerHTML = `${t(key)}<small>${other(key)}</small>`; el.classList.add('show');
}
function speak(key) {
  subtitle(key);
  const start = () => { angel.talking = true; duck(true); };
  const end = () => { angel.talking = false; duck(false); setTimeout(() => subtitle(null), 800); };
  if (currentClip) { const old = currentClip; let v = old.volume; const fade = () => { v -= 0.12; if (v <= 0) old.pause(); else { old.volume = v; setTimeout(fade, 20); } }; fade(); }  // 150 ms fade, never overlap
  const a = new Audio(`assets/voice/${lang === 'en' ? 'gabriel-en' : 'gabriel'}/${VOICE_FILE[key]}.mp3`);
  currentClip = a; a.onplay = start; a.onended = end;
  a.onerror = () => say(t(key), { lang, onstart: start, onend: end });
  a.play().catch(() => say(t(key), { lang, onstart: start, onend: end }));
}
// tiny UI cues (click / lock / lost) — same as Unity's MakeCues
function cue(kind) {
  const ctx = audioCtx(); if (!ctx) return;
  const [hz, secs, decay, amp] = { click: [1400, 0.045, 60, 0.5], lock: [1568, 0.28, 9, 0.35], lost: [220, 0.16, 14, 0.4] }[kind];
  const o = ctx.createOscillator(), g = ctx.createGain(); o.frequency.value = hz; const t0 = ctx.currentTime;
  g.gain.setValueAtTime(amp, t0); g.gain.exponentialRampToValueAtTime(0.0001, t0 + secs); o.connect(g).connect(ctx.destination); o.start(t0); o.stop(t0 + secs + 0.02);
}
function enterScene(holder) {
  holder.add(angel.root);
  angel.root.visible = true;
  setPhase('enter'); fx.trigger('enter'); chime();
  new Audio('assets/music/swell.mp3').play().catch(() => {});
  if (theme.paused) { theme.volume = MUSIC_BED; theme.play().catch(() => {}); }
  setTimeout(() => speak('hello'), 900);
}

function reveal(viewMode) {
  S.mode = 'live'; S.view = viewMode;
  show('guide', false);
  enterScene(viewMode === 'paper' ? paperHolder : showHolder);
  refreshButtons();
  status(t(xrSupported ? 'tapXR' : 'tap')); S.idleSince = performance.now(); S.greetCount = 0; S.lastTouch = 0;
}

const LINES = ['line0', 'line1', 'line2', 'line3'], GREETS = ['greet0', 'greet1', 'greet2'];
function action() {
  if (S.phase === 'action' || S.phase === 'enter' || S.busy) return;
  setPhase('action'); fx.trigger('action');
  const d = fanfare();
  cue('click'); S.idleSince = performance.now();
  setTimeout(() => speak(LINES[S.voiceIdx++ % LINES.length]), d * 1000);
}

async function startScan() {
  unlockAudio(); keepAwake();
  show('start', false); show('hud', true);
  status(t('openingCam'));
  try { await startCamera(); } catch (e) {
    status(t('camFail', { e: e.message || e })); show('start', true); return;
  }
  resetScan();
}
function resetScan() {
  S.mode = 'scan'; S.good = 0; S.lastPts = null; S.havePose = false; angel.root.visible = false;
  show('guide', true); refreshButtons();
  status(t('fit')); S.scanStart = performance.now(); S.helpShown = false;
}
function capture(ptsV) {
  $('flash').classList.add('on'); setTimeout(() => $('flash').classList.remove('on'), 60);
  const used = bakeFromCamera(ptsV || guideQuad().map(toVideo));
  if (ptsV) { S.lastPts = used; updatePose(used); }
  reveal(ptsV ? 'paper' : 'show');
}

// Keep the screen on while the camera / AR is in use (the phone slept mid-session, LESSONS L21)
let wakeLock = null;
async function keepAwake() {
  try { if ('wakeLock' in navigator && !wakeLock) { wakeLock = await navigator.wakeLock.request('screen'); wakeLock.addEventListener('release', () => { wakeLock = null; }); } } catch { /* not allowed: fine */ }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && S.mode !== 'start') keepAwake(); });

// ---------------- WebXR (ARCore) ----------------
let hitSource = null, xrRef = null;
async function enterXR() {
  unlockAudio(); keepAwake();
  stopCamera();                                   // ARCore needs the camera
  angel.root.visible = false;
  const session = await navigator.xr.requestSession('immersive-ar', {
    requiredFeatures: ['hit-test'], optionalFeatures: ['dom-overlay', 'local-floor'], domOverlay: { root: $('hud') },
  });
  camera.near = 0.02; camera.far = 50; camera.updateProjectionMatrix();
  renderer.xr.setReferenceSpaceType('local');
  await renderer.xr.setSession(session);
  xrRef = renderer.xr.getReferenceSpace();
  hitSource = await session.requestHitTestSource({ space: await session.requestReferenceSpace('viewer') });
  S.xr = session; S.xrPlaced = false; S.xrHint = null;
  document.body.classList.add('xr');
  session.addEventListener('select', onXRSelect);
  session.addEventListener('end', onXREnd);
  refreshButtons();
  status(t('xrFind'));
}
const ray = new THREE.Raycaster();
function onXRSelect(e) {
  const pose = e.frame.getPose(e.inputSource.targetRaySpace, xrRef);
  if (S.xrPlaced && pose) {
    const { position: p, orientation: o } = pose.transform;
    const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(new THREE.Quaternion(o.x, o.y, o.z, o.w));
    ray.set(new THREE.Vector3(p.x, p.y, p.z), dir);
    if (ray.intersectObject(angel.root, true).length) { action(); return; }
  }
  if (!reticle.visible) { if (!S.xrPlaced) status(t('xrNoPlane')); return; }
  const at = new THREE.Vector3().setFromMatrixPosition(reticle.matrix);
  const cam = renderer.xr.getCamera().getWorldPosition(new THREE.Vector3());
  xrHolder.position.copy(at);
  xrHolder.rotation.set(0, Math.atan2(cam.x - at.x, cam.z - at.z), 0);   // face the viewer, stay upright
  if (!S.xrPlaced) { S.xrPlaced = true; enterScene(xrHolder); status(t('xrPlaced')); }
}
function onXREnd() {
  hitSource = null; S.xr = null; reticle.visible = false;
  document.body.classList.remove('xr');
  camera.near = 10; camera.far = 1e5;
  S.view = 'show'; showHolder.add(angel.root); angel.root.visible = true;
  layout(); refreshButtons();
  status(t('xrExit'));
}

// ---------------- read-aloud, idle greeting, help card, pause ----------------
async function readTitle() {
  if (S.mode !== 'live' || S.busy || !angel.title) return;
  S.busy = true; cue('click');
  const py = (localStorage.getItem('titleMode') || 'py') === 'py';
  const order = ['hanzi', py ? 'pinyin' : 'english', py ? 'english' : 'pinyin'], keys = ['readHanzi', py ? 'readPinyin' : 'readEnglish', py ? 'readEnglish' : 'readPinyin'];
  for (let i = 0; i < 3; i++) {
    status(t(keys[i])); chime();
    const part = angel.title.getObjectByName(order[i]); const was = part?.visible;
    if (part) { part.visible = true; const s0 = part.scale.clone(); const t0 = performance.now();
      await new Promise(r => { const step = () => { const k = (performance.now() - t0) / 1300; part.scale.copy(s0).multiplyScalar(1 + 0.18 * Math.sin(Math.PI * Math.min(1, k * 1.25))); if (k < 1) requestAnimationFrame(step); else { part.scale.copy(s0); r(); } }; step(); });
      part.visible = was; }
    else await new Promise(r => setTimeout(r, 1300));
  }
  status(t(xrSupported ? 'tapXR' : 'tap')); S.busy = false; S.idleSince = performance.now();
}
function maybeGreet(now) {
  if (S.mode !== 'live' || S.busy || angel.talking || S.phase !== 'idle') return;
  if (now - S.idleSince > 20000 && (S.greetCount || 0) < 2 && now - (S.lastGreet || 0) > 25000) {
    S.greetCount = (S.greetCount || 0) + 1; S.lastGreet = now; S.idleSince = now;
    speak(GREETS[S.greetCount % GREETS.length]);
  }
}
function maybeHelp(now) {
  if (S.mode === 'scan' && !S.helpShown && now - S.scanStart > 30000) { S.helpShown = true; $('help').classList.add('show'); }
  if (S.mode !== 'scan' || S.good > 0) $('help').classList.remove('show');
}
function setLost(lost) {
  if (lost === S.lost) return; S.lost = lost;
  document.body.classList.toggle('lost', lost);
  if (lost) { cue('lost'); status(t('lost')); } else status(t(xrSupported ? 'tapXR' : 'tap'));
}
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { theme.volume = 0; currentClip?.pause(); } else { if (!theme.paused) duck(false); currentClip?.play().catch(() => {}); S.idleSince = performance.now(); }
});

// ---------------- buttons + pointer ----------------
applyLang();
for (const b of document.querySelectorAll('[data-lang-toggle]')) b.onclick = () => { setLang(lang === 'zh' ? 'en' : 'zh'); refreshButtons(); paintTexture(); if (S.mode === 'live') status(t(xrSupported ? 'tapXR' : 'tap')); };
$('langHud').onclick = () => { setLang(lang === 'zh' ? 'en' : 'zh'); refreshButtons(); paintTexture(); if (S.mode === 'live') status(t(xrSupported ? 'tapXR' : 'tap')); };
// Grown-up gate (screen 09): hold the lock for 2 s; the ring fills while held (DESIGN-DIRECTION §5)
let gateTimer = null;
const gateCancel = () => { clearTimeout(gateTimer); gateTimer = null; $('btnGate').classList.remove('holding'); };
$('btnGate').addEventListener('pointerdown', e => {
  e.preventDefault();
  if ($('more').classList.contains('show')) { $('more').classList.remove('show'); cue('click'); return; }
  $('btnGate').classList.add('holding');
  gateTimer = setTimeout(() => { gateCancel(); $('more').classList.add('show'); cue('lock'); }, 2000);
});
for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) $('btnGate').addEventListener(ev, gateCancel);
$('helpDemo').onclick = () => { $('help').classList.remove('show'); $('btnDemo').click(); };
$('btnScan').onclick = startScan;
$('btnDemo').onclick = async () => {
  unlockAudio(); show('start', false); show('hud', true);
  document.body.classList.add('demo');
  layout();
  await loadDemoTexture();
  reveal('show');
};
$('btnShoot').onclick = () => { unlockAudio(); capture(S.good >= 2 ? S.lastPts : null); };
$('btnNew').onclick = () => { cue('click'); speechSynthesis?.cancel(); video.srcObject ? resetScan() : startScan(); };
$('btnMode').onclick = () => {
  S.view = S.view === 'paper' ? 'show' : 'paper';
  (S.view === 'paper' ? paperHolder : showHolder).add(angel.root);
  if (S.view === 'paper' && !S.havePose) status(t('needMarkers'));
  refreshButtons();
};
$('btnLines').onclick = () => { S.lines = !S.lines; paintTexture(); };
$('btnTitle').onclick = () => {   // 拼音 <-> English under the 3D title
  const mode = (localStorage.getItem('titleMode') || 'py') === 'py' ? 'en' : 'py';
  try { localStorage.setItem('titleMode', mode); } catch {}
  angel.title?.userData.setMode?.(mode);
  const [a, b] = $('btnTitle').querySelectorAll('span'); a.classList.toggle('on', mode === 'py'); b.classList.toggle('on', mode === 'en');
};
$('btnXR').onclick = () => enterXR().catch(e => { status(t('xrFail', { e: e.message || e })); refreshButtons(); });
$('btnExitXR').onclick = () => S.xr?.end();
for (const b of document.querySelectorAll('#hud button')) b.addEventListener('beforexrselect', e => e.preventDefault());

let down = null;
glCanvas.addEventListener('pointerdown', e => { down = { x: e.clientX, y: e.clientY, ry: showHolder.rotation.y, moved: false }; });
glCanvas.addEventListener('pointermove', e => {
  if (!down) return;
  const dx = e.clientX - down.x;
  if (Math.abs(dx) > 8) down.moved = true;
  if (down.moved && angel.root.parent === showHolder) showHolder.rotation.y = down.ry + dx * 0.01;
});
glCanvas.addEventListener('pointerup', e => {
  if (!down) return;
  const tap = !down.moved; down = null;
  if (!tap || S.mode !== 'live' || S.xr) return;
  unlockAudio(); S.lastTouch = performance.now(); $('more').classList.remove('show');
  ray.setFromCamera(new THREE.Vector2((e.clientX / view.sw) * 2 - 1, -(e.clientY / view.sh) * 2 + 1), camera);
  if (angel.title && ray.intersectObject(angel.title, true).length) readTitle();
  else if (ray.intersectObject(angel.root, true).length || nearAngel(e.clientX, e.clientY)) action();
});

// ---------------- tap hint (screen 06): dotted ring + hand around the angel after 5 s without a touch ----------------
const HINT_AFTER = 5000, hintBox = new THREE.Box3(), hintV = new THREE.Vector3();
let hintRect = null, hintAt = 0;
function angelScreenRect() {
  hintBox.setFromObject(angel.rig || angel.root);   // the body only: not the title, sparks or shadow blob
  if (hintBox.isEmpty()) return null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < 8; i++) {
    hintV.set(i & 1 ? hintBox.max.x : hintBox.min.x, i & 2 ? hintBox.max.y : hintBox.min.y, i & 4 ? hintBox.max.z : hintBox.min.z).project(camera);
    const x = (hintV.x + 1) / 2 * view.sw, y = (1 - hintV.y) / 2 * view.sh;
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
  }
  return { x0, y0, x1, y1 };
}
// forgiving taps: a touch close to her outline counts (Apple AR HIG, "within reasonable proximity")
function nearAngel(x, y) { const r = hintRect || angelScreenRect(); const pad = 24; return !!r && x > r.x0 - pad && x < r.x1 + pad && y > r.y0 - pad && y < r.y1 + pad; }
function updateHint(now) {
  const want = S.mode === 'live' && !S.xr && S.phase === 'idle' && !S.busy && !angel.talking && now - (S.lastTouch || S.idleSince || now) > HINT_AFTER;
  show('hint', want);
  if (!want || now - hintAt < 120) return;
  hintAt = now; hintRect = angelScreenRect(); if (!hintRect) return;
  const h = $('hint'), m = 10, pad = 6;   // keep the ring and the hand on screen
  const r = { x0: Math.max(m, hintRect.x0), y0: Math.max(m + 60, hintRect.y0), x1: Math.min(view.sw - m - 30, hintRect.x1), y1: Math.min(view.sh - m - 90, hintRect.y1) };
  h.style.setProperty('--x', `${r.x0 - pad}px`); h.style.setProperty('--y', `${r.y0 - pad}px`);
  h.style.setProperty('--w', `${r.x1 - r.x0 + pad * 2}px`); h.style.setProperty('--h', `${r.y1 - r.y0 + pad * 2}px`);
}

// ---------------- loop ----------------
let last = performance.now(), detAcc = 0;
function frame(now, xrFrame) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  const time = now / 1000;
  S.phaseT += dt;
  if (S.phase === 'enter' && S.phaseT > 1.4) setPhase('idle');
  if (S.phase === 'action' && S.phaseT > 3.3) setPhase('idle');
  updateHint(now);

  if (xrFrame && hitSource) {
    const hits = xrFrame.getHitTestResults(hitSource);
    const pose = hits.length && hits[0].getPose(xrRef);
    reticle.visible = !!pose;
    if (pose) reticle.matrix.fromArray(pose.transform.matrix);
    // tell the user what ARCore needs (LESSONS L16): no pose = not tracking at all; pose but no hit = no surface yet
    const tracking = !!xrFrame.getViewerPose(xrRef);
    const hint = !tracking ? 'notrack' : !pose ? 'nosurface' : 'ok';
    if (!S.xrPlaced && hint !== S.xrHint) {
      S.xrHint = hint;
      status(t(hint));
    }
  }

  maybeGreet(now); maybeHelp(now);
  if (S.mode === 'live' && S.view === 'paper' && !S.xr) setLost(S.lost ? S.lost && S.good === 0 : S.lostFor > 1.5);
  detAcc += dt;
  const wantDetect = !S.xr && video.srcObject && (S.mode === 'scan' || (S.mode === 'live' && S.view === 'paper'));
  if (wantDetect && detAcc > (S.mode === 'scan' ? 0.12 : 0.066)) {
    detAcc = 0;
    const pts = detect();
    if (pts) {
      S.lastPts = pts; S.good++; S.lostFor = 0; if (S.good === 1 && S.mode === 'scan') cue('lock');
      if (S.mode === 'scan') {
        drawGuide(pts.map(toScreen));
        status(t(S.good < 6 ? 'found' : 'recognised'));
        if (S.good >= 6) capture(pts);
      } else updatePose(pts);
    } else {
      S.good = 0; S.lostFor = (S.lostFor || 0) + (S.mode === 'scan' ? 0.12 : 0.066);
      if (S.lostFor > 1) S.lastPts = null;
      if (S.mode === 'scan') drawGuide();
    }
  }
  if (S.havePose && !S.xr) {
    curPose.p.lerp(targetPose.p, 0.35); curPose.q.slerp(targetPose.q, 0.35);
    placeOnPaper();
  }

  if (angel.root.visible) {
    animate(angel, { phase: S.phase, t: S.phaseT }, time);
    if (angel.title) {   // billboard about Y, gentle bob (glTF text faces +Z in three.js)
      const cw = (renderer.xr.isPresenting ? renderer.xr.getCamera() : camera).getWorldPosition(new THREE.Vector3());
      const tw = angel.title.getWorldPosition(new THREE.Vector3()); cw.y = tw.y;
      angel.title.lookAt(cw); angel.title.position.y = 1.42 + 0.02 * Math.sin(time * 1.1);
    }
    fx.update(dt, time);
    const burst = S.phase === 'enter' ? 1 : S.phase === 'action' ? 0.9 : 0.3;
    for (let i = 0; i < SPARK; i++) {
      const s = sparkSeed[i], life = (time * (0.25 + s * 0.3) + s * 10) % 1;
      const a = s * 60, r = 0.15 + 0.5 * ((s * 7.3) % 1);
      sparkPos[i * 3] = Math.cos(a + time * 0.4) * r;
      sparkPos[i * 3 + 1] = life * 1.6;
      sparkPos[i * 3 + 2] = Math.sin(a + time * 0.4) * r * 0.6;
    }
    sparkGeom.attributes.position.needsUpdate = true;
    sparks.material.opacity = burst;
    blob.visible = angel.root.parent !== showHolder;
  }
  renderer.render(scene, camera);
}
layout();
renderer.setAnimationLoop(frame);

// debug hook for automated checks
window.__doodlive = { S, angel, action, scene, camera, grav, enterXR, build };
document.getElementById('build').textContent = `${build.sha}.${build.time}`;
