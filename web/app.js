// DoodLive prototype: scan -> bake texture -> angel enters -> tap = trumpet + voice.
import * as THREE from 'three';
import { buildAngel, animate, radialTexture } from './angel.js';
import { homography, applyH, detectMarkers, warpArt, whiteBalance, eraseLines, poseFromH } from './vision.js';
import { unlockAudio, fanfare, chime, say } from './audio.js';

const $ = id => document.getElementById(id);
const video = $('video'), glCanvas = $('gl');
const tpl = await (await fetch('assets/template.json')).json();
const TEX = 1024;

// ---------------- three.js ----------------
const renderer = new THREE.WebGLRenderer({ canvas: glCanvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, 1, 10, 1e5);
scene.add(new THREE.HemisphereLight(0xfff6e8, 0x6070a0, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(0.4, 1, 0.8); scene.add(sun);
const fill = new THREE.DirectionalLight(0xbfd4ff, 0.6); fill.position.set(-1, 0.2, 0.5); scene.add(fill);

const canvasTex = document.createElement('canvas'); canvasTex.width = canvasTex.height = TEX;
const texture = new THREE.CanvasTexture(canvasTex);
texture.colorSpace = THREE.SRGBColorSpace; texture.anisotropy = 4;
const angel = buildAngel(texture);
angel.root.visible = false;

// shadow blob + sparkles live with the angel
const blob = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.6), new THREE.MeshBasicMaterial({ map: radialTexture('rgba(20,20,40,0.55)'), transparent: true, depthWrite: false }));
blob.rotation.x = -Math.PI / 2; blob.position.y = 0.002; angel.root.add(blob);
const SPARK = 160, sparkPos = new Float32Array(SPARK * 3), sparkSeed = new Float32Array(SPARK);
for (let i = 0; i < SPARK; i++) sparkSeed[i] = Math.random();
const sparkGeom = new THREE.BufferGeometry(); sparkGeom.setAttribute('position', new THREE.BufferAttribute(sparkPos, 3));
const sparks = new THREE.Points(sparkGeom, new THREE.PointsMaterial({ map: radialTexture('rgba(255,245,200,1)'), size: 0.045, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
angel.root.add(sparks);

// AR anchor: matrix = paper pose (template px units). Show holder: fixed in front of the camera.
const anchor = new THREE.Group(); anchor.matrixAutoUpdate = false; scene.add(anchor);
const arHolder = new THREE.Group(); anchor.add(arHolder);
arHolder.position.set(tpl.art[0] + tpl.art[2] / 2, tpl.art[1] + tpl.art[3] * 0.66, 0);
arHolder.rotation.x = -Math.PI / 2;
arHolder.scale.setScalar(tpl.art[2] * 0.75);
const showHolder = new THREE.Group(); scene.add(showHolder);
showHolder.position.set(0, -720, -2700); showHolder.scale.setScalar(1250);

// ---------------- state ----------------
const S = { mode: 'start', ar: true, lines: false, phase: 'idle', phaseT: 0, good: 0, lastPts: null, lost: 0,
  rawTex: null, cleanTex: null, voiceIdx: 0, havePose: false };
const targetPose = { p: new THREE.Vector3(), q: new THREE.Quaternion(), s: new THREE.Vector3(1, 1, 1) };
const curPose = { p: new THREE.Vector3(), q: new THREE.Quaternion(), s: new THREE.Vector3(1, 1, 1) };
const FLIP = new THREE.Matrix4().makeScale(1, -1, -1);

let view = { sw: innerWidth, sh: innerHeight, scale: 1, ox: 0, oy: 0, vw: 0, vh: 0, f: 1000 };
function layout() {
  view.sw = innerWidth; view.sh = innerHeight;
  renderer.setSize(view.sw, view.sh, false);
  const vw = video.videoWidth || 1080, vh = video.videoHeight || 1920;
  view.vw = vw; view.vh = vh;
  view.scale = Math.max(view.sw / vw, view.sh / vh);
  view.ox = (view.sw - vw * view.scale) / 2; view.oy = (view.sh - vh * view.scale) / 2;
  view.f = 0.8 * Math.max(vw, vh) * view.scale;            // ~65° on the long side; good enough for a phone
  camera.aspect = view.sw / view.sh;
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(view.sh / 2 / view.f));
  camera.updateProjectionMatrix();
  drawGuide();
}
addEventListener('resize', layout);

// Guide = where the 4 markers should land on screen.
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
  m.decompose(targetPose.p, targetPose.q, targetPose.s);
  if (!S.havePose) { curPose.p.copy(targetPose.p); curPose.q.copy(targetPose.q); S.havePose = true; }
}

// ---------------- capture / bake ----------------
function bakeFromCamera(ptsV) {
  const c = document.createElement('canvas'); c.width = video.videoWidth; c.height = video.videoHeight;
  const cx = c.getContext('2d', { willReadFrequently: true }); cx.drawImage(video, 0, 0);
  const frame = cx.getImageData(0, 0, c.width, c.height);
  // refine at full resolution around the coarse hits
  const refined = detectMarkers(frame, ptsV, Math.max(24, c.width * 0.03)) || ptsV;
  const H = homography(tpl.markers, refined);
  const art = whiteBalance(warpArt(frame, H, tpl, TEX));
  setTextureData(art);
  return refined;
}

function setTextureData(img) {
  S.rawTex = img; S.cleanTex = eraseLines(img);
  paintTexture();
}
function paintTexture() {
  canvasTex.getContext('2d').putImageData(S.lines ? S.rawTex : S.cleanTex, 0, 0);
  texture.needsUpdate = true;
  $('btnLines').textContent = S.lines ? '线条：显示' : '线条：隐藏';
}

async function loadDemoTexture() {
  const img = new Image(); img.src = 'assets/demo-colored.png'; await img.decode();
  const c = document.createElement('canvas'); c.width = c.height = TEX;
  const x = c.getContext('2d'); x.drawImage(img, 0, 0, TEX, TEX);
  setTextureData(x.getImageData(0, 0, TEX, TEX));
}

// ---------------- flow ----------------
function status(t) { $('status').textContent = t; }
function show(id, on) { $(id).classList.toggle('hidden', !on); }

function reveal() {
  S.mode = 'live'; setPhase('enter');
  angel.root.visible = true;
  show('guide', false); show('btnShoot', false);
  show('btnRescan', true); show('btnMode', !!video.srcObject); show('btnLines', true);
  attachAngel();
  chime();
  setTimeout(() => say('哇！我活过来啦！谢谢你给我涂上这么漂亮的颜色！'), 900);
  status('点一下天使，听她吹响号角');
}
function attachAngel() {
  (S.ar && S.havePose ? arHolder : showHolder).add(angel.root);
  $('btnMode').textContent = S.ar ? '展示模式' : 'AR 模式';
}
function setPhase(p) { S.phase = p; S.phaseT = 0; }

const LINES = ['听！天堂的号角为你吹响！', '你画得真好看，我好喜欢这些颜色！', '愿你今天平安、快乐！', '再给我画一件新衣服吧！'];
function action() {
  if (S.phase === 'action') return;
  setPhase('action');
  const d = fanfare();
  setTimeout(() => say(LINES[S.voiceIdx++ % LINES.length]), d * 1000);
}

async function startScan() {
  unlockAudio();
  show('start', false); show('hud', true);
  status('正在打开相机…');
  try { await startCamera(); } catch (e) {
    status('打不开相机：' + (e.message || e) + '。可以先看演示'); show('start', true); return;
  }
  S.mode = 'scan'; S.good = 0; S.lastPts = null; S.havePose = false; angel.root.visible = false;
  show('guide', true); show('btnShoot', true); show('btnRescan', false); show('btnMode', false); show('btnLines', false);
  status('把整张涂色纸放进框里，四个黑方块对准四个角');
}

function capture(ptsV) {
  $('flash').classList.add('on'); setTimeout(() => $('flash').classList.remove('on'), 60);
  const used = bakeFromCamera(ptsV || guideQuad().map(toVideo));
  S.ar = !!ptsV;
  if (ptsV) { S.lastPts = used; updatePose(used); }
  reveal();
}

$('btnScan').onclick = startScan;
$('btnDemo').onclick = async () => {
  unlockAudio(); show('start', false); show('hud', true);
  document.body.style.background = 'radial-gradient(circle at 50% 40%, #33407a, #0b1020 70%)';
  layout(); S.ar = false;
  await loadDemoTexture();
  reveal();
};
$('btnShoot').onclick = () => { unlockAudio(); capture(S.good >= 2 ? S.lastPts : null); };
$('btnRescan').onclick = () => { speechSynthesis?.cancel(); video.srcObject ? startScanAgain() : startScan(); };
function startScanAgain() {
  S.mode = 'scan'; S.good = 0; S.lastPts = null; S.havePose = false; angel.root.visible = false;
  show('guide', true); show('btnShoot', true); show('btnRescan', false); show('btnMode', false); show('btnLines', false);
  status('把整张涂色纸放进框里，四个黑方块对准四个角');
}
$('btnMode').onclick = () => { S.ar = !S.ar; if (S.ar && !S.havePose) { status('先让四个黑方块进入画面'); } attachAngel(); };
$('btnLines').onclick = () => { S.lines = !S.lines; paintTexture(); };

// tap the angel / drag to spin in show mode
const ray = new THREE.Raycaster();
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
  if (!tap || S.mode !== 'live') return;
  unlockAudio();
  ray.setFromCamera(new THREE.Vector2((e.clientX / view.sw) * 2 - 1, -(e.clientY / view.sh) * 2 + 1), camera);
  if (ray.intersectObject(angel.root, true).length) action();
});

// ---------------- loop ----------------
let last = performance.now(), detAcc = 0;
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  const time = now / 1000;
  S.phaseT += dt;
  if (S.phase === 'enter' && S.phaseT > 1.4) setPhase('idle');
  if (S.phase === 'action' && S.phaseT > 3.3) setPhase('idle');

  detAcc += dt;
  const wantDetect = video.srcObject && (S.mode === 'scan' || (S.mode === 'live' && S.ar));
  if (wantDetect && detAcc > (S.mode === 'scan' ? 0.12 : 0.066)) {
    detAcc = 0;
    const pts = detect();
    if (pts) {
      S.lastPts = pts; S.good++; S.lost = 0;
      if (S.mode === 'scan') {
        drawGuide(pts.map(toScreen));
        status(S.good < 6 ? '找到了！拿稳别动…' : '识别成功');
        if (S.good >= 6) capture(pts);
      } else {
        updatePose(pts);
        if (!S.havePose || angel.root.parent !== arHolder) attachAngel();
      }
    } else {
      S.good = 0; S.lost++;
      if (S.lost > 8) S.lastPts = null;   // search the whole guide again
      if (S.mode === 'scan') drawGuide();
    }
  }
  if (S.havePose) {
    curPose.p.lerp(targetPose.p, 0.35); curPose.q.slerp(targetPose.q, 0.35);
    anchor.matrix.compose(curPose.p, curPose.q, curPose.s);
    anchor.matrixWorldNeedsUpdate = true;
  }

  if (angel.root.visible) {
    animate(angel, { phase: S.phase, t: S.phaseT }, time);
    const burst = S.phase === 'enter' ? 1 : S.phase === 'action' ? 0.8 : 0.25;
    for (let i = 0; i < SPARK; i++) {
      const s = sparkSeed[i], life = (time * (0.25 + s * 0.3) + s * 10) % 1;
      const a = s * 60, r = 0.15 + 0.45 * ((s * 7.3) % 1);
      sparkPos[i * 3] = Math.cos(a + time * 0.4) * r;
      sparkPos[i * 3 + 1] = life * 1.5;
      sparkPos[i * 3 + 2] = Math.sin(a + time * 0.4) * r * 0.6;
    }
    sparkGeom.attributes.position.needsUpdate = true;
    sparks.material.opacity = burst;
    blob.visible = angel.root.parent === arHolder;
  }
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
layout();
requestAnimationFrame(frame);

// debug hook for automated checks
window.__doodlive = { S, angel, action, scene, camera };
