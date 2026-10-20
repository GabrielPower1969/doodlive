// David vs Goliath — a 33-second choreographed AR battle: taunts, weapon waves, sling shot, fall, victory.
// Modes: cinematic (camera cuts, sky) or WebXR (arena placed on a real table, you walk around it).
import * as THREE from 'three';
import { buildHumanoid, resetPose, idle, walk, setMouth } from './character.js';
import { sfx, music } from './sound.js';
import { unlockAudio } from '../audio.js';
import { preloadVoice, voice, stopVoice } from './voice.js';
import { radialTexture } from '../angel.js';

const $ = id => document.getElementById(id);
const renderer = new THREE.WebGLRenderer({ canvas: $('gl'), antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.xr.enabled = true;
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 200);
const arena = new THREE.Group(); scene.add(arena);         // everything of the battle lives here

// ---------------- world ----------------
const skyTex = (() => { const c = document.createElement('canvas'); c.width = 4; c.height = 256; const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, 256); g.addColorStop(0, '#3a2c5c'); g.addColorStop(0.55, '#d0755a'); g.addColorStop(1, '#f2c27b');
  x.fillStyle = g; x.fillRect(0, 0, 4, 256); const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t; })();
scene.background = skyTex; scene.fog = new THREE.Fog(0xe2a070, 18, 60);
scene.add(new THREE.HemisphereLight(0xffe2c0, 0x5a4030, 1.3));
const sun = new THREE.DirectionalLight(0xffd7a0, 2.6); sun.position.set(-6, 10, 4); sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024); Object.assign(sun.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8, near: 1, far: 30 });
arena.add(sun); arena.add(sun.target);

const groundTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 512; const x = c.getContext('2d');
  x.fillStyle = '#c9a46a'; x.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 9000; i++) { const v = 150 + Math.random() * 70; x.fillStyle = `rgba(${v},${v * 0.8},${v * 0.55},0.35)`; x.fillRect(Math.random() * 512, Math.random() * 512, 2, 2); }
  for (let i = 0; i < 120; i++) { x.fillStyle = 'rgba(110,130,60,0.35)'; x.beginPath(); x.arc(Math.random() * 512, Math.random() * 512, 3 + Math.random() * 9, 0, 7); x.fill(); }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(3, 3); t.colorSpace = THREE.SRGBColorSpace; return t; })();
const ground = new THREE.Mesh(new THREE.CircleGeometry(9, 64), new THREE.MeshStandardMaterial({ map: groundTex, roughness: 1 }));
ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; arena.add(ground);
const rim = new THREE.Mesh(new THREE.CylinderGeometry(9, 9.3, 0.4, 64, 1, true), new THREE.MeshStandardMaterial({ color: 0x8a6a45, side: THREE.DoubleSide }));
rim.position.y = -0.2; arena.add(rim);
const rockMat = new THREE.MeshStandardMaterial({ color: 0x8f8476, roughness: 0.95, flatShading: true });
const rocks = [];
for (let i = 0; i < 26; i++) {
  const a = Math.random() * Math.PI * 2, r = 4 + Math.random() * 4.6, s = 0.15 + Math.random() * 0.5;
  const m = new THREE.Mesh(new THREE.DodecahedronGeometry(s, 0), rockMat);
  m.position.set(Math.cos(a) * r, s * 0.4, Math.sin(a) * r); m.rotation.set(Math.random() * 3, Math.random() * 3, 0); m.castShadow = m.receiveShadow = true;
  arena.add(m); rocks.push(m);
}
const hills = new THREE.Group(); scene.add(hills);      // cinematic backdrop only
for (let i = 0; i < 9; i++) {
  const a = (i / 9) * Math.PI * 2, m = new THREE.Mesh(new THREE.SphereGeometry(10 + Math.random() * 6, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x9a7a55, roughness: 1 }));
  m.scale.y = 0.35 + Math.random() * 0.25; m.position.set(Math.cos(a) * 34, -1, Math.sin(a) * 34); hills.add(m);
}

// ---------------- actors ----------------
const david = buildHumanoid({ kind: 'david', height: 1.0, bulk: 0.95, skin: 0xd9a77c, cloth: 0xe8dcc0, cloth2: 0xb5895a, hair: 0x3b2414 });
const goliath = buildHumanoid({ kind: 'goliath', height: 2.7, bulk: 1.3, skin: 0xb98563, cloth: 0x6b4a2f, hair: 0x2b1b10, armour: true });
arena.add(david.root, goliath.root);

// ---------------- effects ----------------
const add = (map, color) => new THREE.MeshBasicMaterial({ map, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
const glowTex = radialTexture('rgba(255,255,255,1)');
const waveTex = (() => { const c = document.createElement('canvas'); c.width = 256; c.height = 64; const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 0, 64); g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(0.5, 'rgba(255,255,255,1)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 256, 64); return new THREE.CanvasTexture(c); })();

const fx = { waves: [], parts: [] };
function crescent(color, r, thick, arc) {
  const m = new THREE.Mesh(new THREE.RingGeometry(r - thick, r, 48, 1, Math.PI / 2 - arc / 2, arc), add(waveTex, color));
  arena.add(m); return m;
}
function spawnWave(kind, from, speed) {
  let m;
  if (kind === 'ground') { m = crescent(0xff8a3a, 1.0, 0.45, Math.PI * 0.9); m.position.copy(from); m.position.y = 0; }
  if (kind === 'slash') { m = crescent(0x9fd8ff, 1.3, 0.25, Math.PI * 0.75); m.rotation.x = -Math.PI / 2; m.position.copy(from); }
  if (kind === 'hit') { m = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 12), add(glowTex, 0xfff4c8)); m.position.copy(from); arena.add(m); }
  if (kind === 'ring') { m = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.08, 8, 64), add(glowTex, 0xffc070)); m.rotation.x = Math.PI / 2; m.position.copy(from); arena.add(m); }
  fx.waves.push({ kind, m, t: 0, speed });
}
const partPool = [];
function particle(pos, vel, { color = 0xffffff, size = 0.15, life = 1, grow = 1, gravity = 0, additive = true } = {}) {
  let p = partPool.pop();
  if (!p) { p = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, transparent: true, depthWrite: false })); arena.add(p); }
  p.visible = true; p.material.color.set(color); p.material.blending = additive ? THREE.AdditiveBlending : THREE.NormalBlending;
  p.position.copy(pos); p.scale.setScalar(size);
  fx.parts.push({ p, vel: vel.clone(), life, t: 0, size, grow, gravity });
}
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const rnd = (a, b) => a + Math.random() * (b - a);
function dust(pos, n = 14, spread = 1) {
  for (let i = 0; i < n; i++) particle(pos.clone().add(V(rnd(-0.3, 0.3) * spread, 0.05, rnd(-0.3, 0.3) * spread)), V(rnd(-1, 1) * spread, rnd(0.3, 1.2), rnd(-1, 1) * spread),
    { color: 0xb08a60, size: rnd(0.3, 0.6) * spread, life: rnd(0.8, 1.6), grow: 2.5, additive: false });
}
function sparks(pos, n = 30, color = 0xffd27a, speed = 4) {
  for (let i = 0; i < n; i++) { const d = V(rnd(-1, 1), rnd(-0.3, 1), rnd(-1, 1)).normalize().multiplyScalar(rnd(0.3, 1) * speed);
    particle(pos, d, { color, size: rnd(0.05, 0.12), life: rnd(0.3, 0.8), grow: 0.3, gravity: 6 }); }
}
const slingRing = new THREE.Mesh(new THREE.TorusGeometry(0.33, 0.02, 8, 48), add(glowTex, 0xffe39a));
slingRing.visible = false; arena.add(slingRing);
const rays = new THREE.Group(); arena.add(rays); rays.visible = false;
for (let i = 0; i < 7; i++) {
  const r = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.32, 7, 12, 1, true), add(waveTex, 0xfff1b8));
  r.position.set(rnd(-0.5, 0.5), 3.5, rnd(-0.5, 0.5)); r.rotation.set(rnd(-0.15, 0.15), 0, rnd(-0.15, 0.15)); rays.add(r);
}
const flashEl = $('flash');
function flash(strength = 1) { flashEl.style.transition = 'none'; flashEl.style.opacity = String(0.95 * strength); requestAnimationFrame(() => { flashEl.style.transition = 'opacity .6s'; flashEl.style.opacity = '0'; }); }
let shakeAmt = 0;
const shake = a => { shakeAmt = Math.max(shakeAmt, a); };

// stone projectile
const flyingStone = new THREE.Mesh(new THREE.SphereGeometry(0.03, 12, 8), new THREE.MeshBasicMaterial({ color: 0xfff2c4 }));
flyingStone.visible = false; arena.add(flyingStone);
const fallenSpear = { active: false, v: new THREE.Vector3(), w: 0 };

// ---------------- script ----------------
// English voice-over (web/assets/voice/en/*.mp3, Microsoft neural voices via tools/make_voice.sh).
// `text` is what the clip says (also the TTS fallback); `zh` is the second subtitle line.
const VOICE_LANG = 'en';
const LINES = {
  goliath: { text: "Am I a dog, that you come at me with a stick? I'll feed you to the birds!", zh: '小子，拿根木棍就敢来见我？我要把你喂给飞鸟！' },
  david: { text: 'You come with a sword and a spear. I come in the name of the Lord of Hosts!', zh: '你靠的是刀枪，我靠的是万军之神的名！' },
  narrator: { text: 'With one small stone, David brought down the giant Goliath. Courage matters more than size.', zh: '大卫用一块小小的石子，打倒了巨人歌利亚。勇气，比身材更重要！' },
};
preloadVoice(VOICE_LANG, Object.keys(LINES));
const subtitle = t => { $('sub').textContent = t; $('sub').classList.toggle('hidden', !t); };
function speak(who) {
  const { text, zh } = LINES[who];
  const fallback = { goliath: { pitch: 0.5, rate: 0.9 }, david: { pitch: 1.3, rate: 1.1 }, narrator: { pitch: 1.0, rate: 0.95 } }[who];
  const actor = who === 'goliath' ? goliath : who === 'david' ? david : null;
  const name = who === 'goliath' ? 'Goliath: ' : who === 'david' ? 'David: ' : '';
  const line = name + text + '\n' + zh;
  // queued, never interrupting; the subtitle shows while that line plays and only that line may clear it
  voice(VOICE_LANG, who, text, { fallback,
    onstart: () => { subtitle(line); if (actor) actor.talking = true; },
    onend: () => { if (actor) actor.talking = false; setTimeout(() => { if ($('sub').textContent === line) subtitle(''); }, 500); } });
}

// one-shot cues fire once when the scene clock passes them
const CUES = [
  [0.1, () => { music.start(); music.set(0.3, 104); }],
  [3.9, () => { sfx.roar(); shake(0.08); }],
  [4.6, () => speak('goliath')],
  [8.4, () => { music.set(0.5, 112); }],
  [9.0, () => speak('david')],
  [12.6, () => { music.set(0.8, 126); }],
  [12.85, () => { sfx.wave(); spawnWave('ground', goliathTipGround(), 7); dust(goliathTipGround(), 18); shake(0.15); }],
  [15.05, () => { sfx.slash(); spawnWave('slash', V(0, 0.75, -1.6), 9); }],
  [18.0, () => { sfx.boom(1.2); spawnWave('ring', V(-0.5, 0.05, -2.2), 0); dust(V(-0.5, 0, -2.2), 30, 1.6); shake(0.3); }],
  [19.6, () => { music.set(1, 138); }],
  [21.6, () => { sfx.spin(0); }], [22.3, () => { sfx.spin(1); }], [22.9, () => { sfx.spin(2); }], [23.35, () => { sfx.spin(3); }],
  [23.6, () => { releaseStone(); sfx.whoosh(0.5, true); }],
  [24.05, () => { hitGoliath(); }],
  [26.0, () => { sfx.thud(); dust(V(0, 0, -1.2), 50, 2.4); shake(0.5); }],
  [26.6, () => { music.victory(); rays.visible = true; }],
  [27.6, () => speak('narrator')],
  [33.5, () => { $('btnReplay').classList.remove('hidden'); }],
];
const SLOWMO = [[13.35, 14.05, 0.3], [23.6, 24.1, 0.22], [24.05, 24.6, 0.4]];

let T = 0, cueIdx = 0, playing = false;
const goliathStart = -9, goliathStop = -2.8;
function goliathTipGround() { const p = goliath.spearTip.getWorldPosition(new THREE.Vector3()); arena.worldToLocal(p); p.y = 0; return p; }

function releaseStone() {
  david.stone.visible = false; flyingStone.visible = true;
  const from = david.B.handR.getWorldPosition(new THREE.Vector3()); arena.worldToLocal(from);
  const to = goliath.B.head.getWorldPosition(new THREE.Vector3()); arena.worldToLocal(to); to.y += 0.2; to.z += 0.2;
  flyingStone.userData = { from, to, t0: T };
}
function hitGoliath() {
  flyingStone.visible = false;
  const p = flyingStone.userData.to;
  sfx.impact(); music.stop(0.02); flash(1); shake(0.45);
  sparks(p, 60, 0xfff0b0, 5); spawnWave('hit', p.clone(), 0);
  fallenSpear.active = true;
}

function resetScene() {
  T = 0; cueIdx = 0; shakeAmt = 0;
  goliath.root.position.set(0, 0, goliathStart); goliath.root.rotation.set(0, 0, 0);
  david.root.position.set(0, 0, 2.2); david.root.rotation.set(0, Math.PI, 0);
  david.stone.visible = true; flyingStone.visible = false; rays.visible = false; slingRing.visible = false;
  if (goliath.spear.parent !== goliath.B.handR) { goliath.B.handR.add(goliath.spear); }
  goliath.spear.position.set(0, -0.03 * goliath.H, 0); goliath.spear.rotation.set(0, 0, 0);
  fallenSpear.active = false;
  for (const w of fx.waves) arena.remove(w.m); fx.waves.length = 0;
  subtitle(''); $('btnReplay').classList.add('hidden');
}

const ease = x => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
const seg = (t, a, b) => ease((t - a) / (b - a));

function pose(dt) {
  const t = T;
  resetPose(goliath); resetPose(david);
  idle(goliath, t, 0.6); idle(david, t * 1.3, 1);
  const G = goliath.B, D = david.B;

  // --- Goliath ---
  if (t < 3.6) {                                              // stomps in
    const u = t / 3.6;
    goliath.root.position.z = goliathStart + (goliathStop - goliathStart) * u;
    const ph = t * 4.4; walk(goliath, ph, 1);
    if (Math.floor(ph / Math.PI) !== Math.floor((ph - dt * 4.4) / Math.PI)) { sfx.step(1); shake(0.06); dust(V(0, 0, goliath.root.position.z), 5, 0.8); }
  } else if (fallenSpear.active === false || t < 24.05) goliath.root.position.z = goliathStop;
  G.shoulderR.rotation.x = -0.5; G.elbowR.rotation.x = -0.9;  // spear held upright
  let aim = -1.45;                                            // spear pitch in Goliath's frame: -π/2 up, 0 forward, + down
  if (t > 3.6 && t < 7.8) {                                    // taunt: spear raised, chest out
    const k = seg(t, 3.6, 4.1) * (1 - seg(t, 7.3, 7.8));
    G.shoulderR.rotation.x = -0.5 - 1.9 * k; G.chest.rotation.x = -0.2 * k; G.head.rotation.x = -0.25 * k;
    G.shoulderL.rotation.z = -0.12 - 0.6 * k;
    aim = -1.45 + 0.35 * k;
  }
  if (t > 12 && t < 14.5) {                                    // thrust into the ground
    const k = seg(t, 12, 12.6) * (1 - seg(t, 13.8, 14.5)), lunge = seg(t, 12.5, 12.85) * (1 - seg(t, 13.8, 14.5));
    G.shoulderR.rotation.x = -0.5 - 1.5 * k + 1.6 * lunge; G.spine.rotation.x = 0.35 * lunge; G.hipL.rotation.x = -0.6 * lunge; G.kneeL.rotation.x = 0.6 * lunge;
    G.hips.position.y -= 0.12 * goliath.H * lunge;
    aim = -1.45 - 1.0 * k + 2.9 * lunge;                      // cocked back, then driven into the ground
  }
  if (t > 14.5 && t < 17) {                                    // horizontal sweep
    const k = seg(t, 14.5, 14.9) * (1 - seg(t, 16.3, 17)), sw = seg(t, 14.85, 15.2);
    G.chest.rotation.y = (0.9 - 1.8 * sw) * k; G.shoulderR.rotation.z = 0.12 + 1.2 * k; G.shoulderR.rotation.x = -0.4;
    aim = -1.45 + 1.45 * k;                                   // level for the sweep
  }
  if (t > 17 && t < 19.5) {                                    // shield slam
    const k = seg(t, 17, 17.6) * (1 - seg(t, 18.6, 19.5)), slam = seg(t, 17.7, 18.0);
    G.shoulderL.rotation.x = -2.4 * k + 1.6 * slam * k; G.spine.rotation.x = 0.3 * slam * k; G.hips.position.y -= 0.1 * goliath.H * slam * k;
  }
  G.handR.rotation.x = aim - (G.shoulderR.rotation.x + G.elbowR.rotation.x);
  if (goliath.talking) setMouth(goliath, Math.abs(Math.sin(t * 11))); else setMouth(goliath, t > 3.8 && t < 5 ? 0.8 : 0);
  if (t >= 24.05) {                                            // hit: freeze, sway, topple forward
    const s = t - 24.05;
    G.head.rotation.x = -0.5 * seg(s, 0, 0.15);
    G.shoulderR.rotation.x = -0.2; G.shoulderL.rotation.z = -0.4;
    const sway = s < 0.9 ? Math.sin(s * 10) * 0.05 * (1 - s / 0.9) : 0;
    const fall = s > 0.9 ? Math.min(1, Math.pow((s - 0.9) / 1.05, 2)) : 0;
    goliath.root.rotation.x = sway + fall * (Math.PI / 2 - 0.06);
    G.shoulderL.rotation.x = -1.2 * fall; G.shoulderR.rotation.x = -1.2 * fall;
    if (fallenSpear.active && goliath.spear.parent === goliath.B.handR && s > 0.3) {
      const wp = goliath.spear.getWorldPosition(new THREE.Vector3()), wq = goliath.spear.getWorldQuaternion(new THREE.Quaternion());
      arena.attach(goliath.spear); goliath.spear.position.copy(arena.worldToLocal(wp)); goliath.spear.quaternion.copy(wq);
      fallenSpear.v.set(0.6, 0, 0.4); fallenSpear.w = 1.8;
    }
  }
  if (goliath.spear.parent === arena) {
    fallenSpear.v.y -= 9.8 * dt; goliath.spear.position.addScaledVector(fallenSpear.v, dt); goliath.spear.rotation.z += fallenSpear.w * dt;
    if (goliath.spear.position.y < 0.05) { goliath.spear.position.y = 0.05; fallenSpear.v.set(0, 0, 0); fallenSpear.w = 0; }
  }

  // --- David ---
  if (t > 7.8 && t < 12) {                                     // steps up and points
    const k = seg(t, 7.9, 8.4) * (1 - seg(t, 11.4, 12));
    D.shoulderR.rotation.x = -1.4 * k; D.elbowR.rotation.x = -0.1 * k; D.chest.rotation.x = -0.1 * k;
    if (t < 8.6) { walk(david, (t - 7.8) * 7, 1 - seg(t, 8.3, 8.6)); david.root.position.z = 2.2 - 0.4 * seg(t, 7.8, 8.6); }
  }
  if (david.talking) setMouth(david, Math.abs(Math.sin(t * 13))); else setMouth(david, 0);
  if (t > 13.2 && t < 14.4) {                                  // jump over the ground wave
    const u = seg(t, 13.25, 14.25), h = Math.sin(Math.PI * u) * 0.95;
    D.hips.position.y += h; D.hipL.rotation.x = -1.1 * Math.sin(Math.PI * u); D.kneeL.rotation.x = 1.6 * Math.sin(Math.PI * u);
    D.hipR.rotation.x = -0.6 * Math.sin(Math.PI * u); D.kneeR.rotation.x = 1.4 * Math.sin(Math.PI * u);
    D.shoulderL.rotation.z = -1.4 * Math.sin(Math.PI * u); D.shoulderR.rotation.z = 1.4 * Math.sin(Math.PI * u);
  }
  if (t > 15.0 && t < 16.3) {                                  // duck under the slash
    const k = seg(t, 15.0, 15.25) * (1 - seg(t, 15.9, 16.3));
    D.hips.position.y -= 0.28 * k; D.spine.rotation.x = 0.9 * k; D.hipL.rotation.x = -1.4 * k; D.kneeL.rotation.x = 2.0 * k;
    D.hipR.rotation.x = -0.3 * k; D.kneeR.rotation.x = 1.9 * k; D.shoulderL.rotation.x = -1.0 * k; D.shoulderR.rotation.x = -1.0 * k;
  }
  if (t > 18.0 && t < 19.4) {                                  // knocked back by the slam
    const k = seg(t, 18.0, 18.2) * (1 - seg(t, 18.7, 19.4));
    D.spine.rotation.x = -0.4 * k; D.shoulderL.rotation.z = -1.0 * k; D.shoulderR.rotation.z = 1.0 * k;
    david.root.position.z = 1.8 + 0.35 * seg(t, 18.0, 18.4);
  }
  if (t > 19.5 && t < 21.5) {                                  // charge
    const u = seg(t, 19.5, 21.4);
    david.root.position.z = 2.15 - 1.25 * u;
    walk(david, (t - 19.5) * 12, 1 - seg(t, 21.2, 21.5), 1);
  }
  slingRing.visible = false; david.stone.material.emissiveIntensity = 0;
  if (t > 21.5 && t < 23.9) {                                  // sling wind-up: three accelerating turns overhead
    const k = seg(t, 21.5, 21.8) * (1 - seg(t, 23.6, 23.9));
    const turns = Math.pow(Math.max(0, t - 21.6) / 2.0, 1.6) * 3.2 * Math.PI * 2;
    D.shoulderR.rotation.z = 2.6 * k; D.shoulderR.rotation.x = -0.3 * k; D.elbowR.rotation.y = turns;
    D.handR.rotation.z = 1.2 * k; david.sling.rotation.y = turns;
    D.hipL.rotation.x = -0.3 * k; D.kneeR.rotation.x = 0.3 * k; D.shoulderL.rotation.x = -0.9 * k;
    david.stone.material.emissiveIntensity = 2 * k;
    slingRing.visible = true; const hp = D.shoulderR.getWorldPosition(new THREE.Vector3()); arena.worldToLocal(hp);
    slingRing.position.copy(hp).add(V(0, 0.3, 0)); slingRing.rotation.x = Math.PI / 2; slingRing.material.opacity = 0.9 * k;
    if (t > 23.6) { D.shoulderR.rotation.x = -2.0; D.shoulderR.rotation.z = 0.4; }   // release follow-through
  }
  if (t >= 26.3) {                                             // victory: arms up
    const k = seg(t, 26.3, 26.9);
    D.shoulderL.rotation.z = -2.6 * k; D.shoulderR.rotation.z = 2.6 * k; D.head.rotation.x = -0.35 * k;
    D.hips.position.y += Math.abs(Math.sin((t - 26.3) * 5)) * 0.08 * (t < 28 ? 1 : 0);
  }

  // stone flight
  if (flyingStone.visible) {
    const { from, to, t0 } = flyingStone.userData, u = Math.min(1, (t - t0) / 0.45);
    flyingStone.position.lerpVectors(from, to, u); flyingStone.position.y += Math.sin(Math.PI * u) * 0.25;
    particle(flyingStone.position, V(0, 0, 0), { color: 0xffe2a0, size: 0.16, life: 0.35, grow: 0.2 });
  }
}

function updateFx(dt) {
  for (let i = fx.waves.length - 1; i >= 0; i--) {
    const w = fx.waves[i]; w.t += dt;
    if (w.kind === 'ground') { w.m.position.z += w.speed * dt; w.m.scale.setScalar(1 + w.t * 0.6); w.m.material.opacity = Math.max(0, 1 - w.t / 1.4); if (Math.random() < 0.6) dust(w.m.position.clone(), 1, 0.6); }
    if (w.kind === 'slash') { w.m.position.z += w.speed * dt; w.m.scale.setScalar(1 + w.t * 0.8); w.m.material.opacity = Math.max(0, 1 - w.t / 1.1);
      if (w.m.position.z > 6 && !w.hit) { w.hit = true; sparks(w.m.position.clone().setY(0.4), 40, 0x9fd8ff, 5); sfx.boom(0.5); } }
    if (w.kind === 'hit') { w.m.scale.setScalar(1 + w.t * 6); w.m.material.opacity = Math.max(0, 1 - w.t / 0.5); }
    if (w.kind === 'ring') { const s = 1 + w.t * 9; w.m.scale.set(s, s, 1); w.m.material.opacity = Math.max(0, 1 - w.t / 0.8); }
    if (w.t > 1.6) { arena.remove(w.m); fx.waves.splice(i, 1); }
  }
  for (let i = fx.parts.length - 1; i >= 0; i--) {
    const q = fx.parts[i]; q.t += dt;
    const u = q.t / q.life;
    if (u >= 1) { q.p.visible = false; partPool.push(q.p); fx.parts.splice(i, 1); continue; }
    q.vel.y -= q.gravity * dt; q.p.position.addScaledVector(q.vel, dt);
    q.p.scale.setScalar(q.size * (1 + (q.grow - 1) * u)); q.p.material.opacity = 1 - u;
  }
  if (rays.visible) { rays.position.set(david.root.position.x, 0, david.root.position.z); rays.children.forEach((r, i) => { r.material.opacity = 0.1 + 0.07 * Math.sin(T * 3 + i); }); }
}

// ---------------- cinematic camera ----------------
const SHOTS = [
  [0, t => [V(7 - t * 0.5, 1.4, 1.5), V(0, 1.3, -4)]],
  [3.6, t => [V(1.0, 0.45, 3.6), V(0, 2.6, -2.8)]],
  [7.8, t => [V(-1.6, 3.4, -5.2), V(0, 0.7, 1.9)]],
  [12, t => [V(4.6, 1.5, 0.5 - t * 0.15), V(0, 0.9, -0.6)]],
  [17, t => [V(0.5, 6, 7.5), V(0, 0, -1)]],
  [19.5, t => [V(0.9, 1.25, 4.2 - t * 0.5), V(0, 1.6, -2.8)]],
  [23.6, t => [V(2.6, 1.8, -0.2), (flyingStone.visible ? flyingStone.position.clone() : V(0, 2.4, -2.6)).lerp(V(0, 2.4, -2.6), 0.5)]],   // side-on tracking of the stone
  [24.1, t => [V(5.5, 1.3, -0.5), V(0, 1.2, -2.2)]],
  [26.4, t => [V(Math.sin(t * 0.3) * 3.2, 1.3, 2.2 + Math.cos(t * 0.3) * 3.2), V(0, 0.75, 2.0)]],
];
function cinematic() {
  let s = SHOTS[0];
  for (const sh of SHOTS) if (T >= sh[0]) s = sh;
  const [p, look] = s[1](T - s[0]);
  // shots are framed for landscape; in portrait the horizontal FOV is narrow, so dolly out (LESSONS L17)
  const k = camera.aspect < 1 ? Math.min(2.3, 0.95 / camera.aspect) : 1;
  camera.position.copy(look).addScaledVector(p.clone().sub(look), k);
  if (shakeAmt > 0.001) camera.position.add(V(rnd(-1, 1), rnd(-1, 1), rnd(-1, 1)).multiplyScalar(shakeAmt * 0.35));
  camera.lookAt(look);
}

// ---------------- WebXR ----------------
let hitSource = null, xrRef = null, placed = false;
const reticle = new THREE.Mesh(new THREE.RingGeometry(0.07, 0.09, 40).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0xffd27a }));
reticle.matrixAutoUpdate = false; reticle.visible = false; scene.add(reticle);
async function enterXR() {
  unlockAudio();
  const session = await navigator.xr.requestSession('immersive-ar', { requiredFeatures: ['hit-test'], optionalFeatures: ['dom-overlay'], domOverlay: { root: $('hud') } });
  renderer.xr.setReferenceSpaceType('local');
  await renderer.xr.setSession(session);
  xrRef = renderer.xr.getReferenceSpace();
  hitSource = await session.requestHitTestSource({ space: await session.requestReferenceSpace('viewer') });
  scene.background = null; scene.fog = null; hills.visible = false; arena.visible = false; placed = false;
  arena.scale.setScalar(0.06); rim.visible = true;                // arena Ø ≈ 1.1 m on the table
  session.addEventListener('select', () => {
    if (!reticle.visible) { $('status').textContent = '还没找到平面：对着明亮、有花纹的桌面慢慢平移手机'; return; }
    arena.position.setFromMatrixPosition(reticle.matrix);
    const cam = renderer.xr.getCamera().getWorldPosition(new THREE.Vector3());
    arena.rotation.set(0, Math.atan2(cam.x - arena.position.x, cam.z - arena.position.z) + Math.PI / 2, 0);   // side view of the duel
    arena.visible = true;
    if (!placed) { placed = true; start(); }
  });
  session.addEventListener('end', () => { hitSource = null; scene.background = skyTex; scene.fog = new THREE.Fog(0xe2a070, 18, 60); hills.visible = true;
    arena.scale.setScalar(1); arena.position.set(0, 0, 0); arena.rotation.set(0, 0, 0); arena.visible = true; reticle.visible = false; layout(); });
  $('start').classList.add('hidden'); $('hud').classList.remove('hidden');
  $('status').textContent = '对准桌面，金色光圈出现后点一下，战场就会出现';
}
for (const b of document.querySelectorAll('#hud button')) b.addEventListener('beforexrselect', e => e.preventDefault());

// ---------------- loop ----------------
function layout() {
  if (renderer.xr.isPresenting) return;
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight; camera.fov = camera.aspect < 1 ? 62 : 45; camera.updateProjectionMatrix();
}
addEventListener('resize', layout); layout();

function start() { resetScene(); speechSynthesis?.cancel(); playing = true; $('status').textContent = ''; }
$('btnPlay').onclick = () => { unlockAudio(); $('start').classList.add('hidden'); $('hud').classList.remove('hidden'); start(); };
$('btnAR').onclick = () => enterXR().catch(e => { $('status').textContent = '进入 AR 失败：' + (e.message || e); });
$('btnReplay').onclick = () => { unlockAudio(); stopVoice(); start(); };
navigator.xr?.isSessionSupported('immersive-ar').then(ok => $('btnAR').classList.toggle('hidden', !ok)).catch(() => {});

resetScene();
let last = performance.now();
renderer.setAnimationLoop((now, xrFrame) => {
  const rdt = Math.min(0.05, (now - last) / 1000); last = now;
  let scale = 1; for (const [a, b, s] of SLOWMO) if (T >= a && T < b) scale = Math.min(scale, s);
  const dt = playing ? rdt * scale : 0;
  if (playing) {
    T += dt;
    while (cueIdx < CUES.length && T >= CUES[cueIdx][0]) CUES[cueIdx++][1]();
  }
  pose(dt || rdt * 0.0001);
  updateFx(dt || rdt);
  shakeAmt *= Math.pow(0.02, rdt);
  if (xrFrame && hitSource) {
    const hits = xrFrame.getHitTestResults(hitSource), p = hits.length && hits[0].getPose(xrRef);
    reticle.visible = !!p && !placed; if (p) reticle.matrix.fromArray(p.transform.matrix);
    if (shakeAmt > 0.01 && placed) arena.position.y += (Math.random() - 0.5) * shakeAmt * 0.01;
  } else if (!renderer.xr.isPresenting) cinematic();
  renderer.render(scene, camera);
});
// debug/QA: jump to a scene time (skips the cues before it, restores the state they would have set)
function seek(v) {
  resetScene(); playing = true; T = v;
  cueIdx = CUES.findIndex(c => c[0] > v); if (cueIdx < 0) cueIdx = CUES.length;
  if (v >= 23.6) david.stone.visible = false;
  if (v >= 24.05) fallenSpear.active = true;
  if (v >= 26.6) rays.visible = true;
}
window.__battle = { get T() { return T; }, set T(v) { seek(v); }, start, david, goliath, enterXR };
