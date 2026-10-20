// Procedural rigged humanoids for the David vs Goliath scene.
// Rig: hips > spine > chest > neck > head, chest > shoulderL/R > elbow > hand, hips > hipL/R > knee > foot.
// Rest pose = standing, arms down, facing +z. Rotations: x<0 swings a limb forward, z rotates sideways.
// Replace with Blender GLBs later: keep the bone names and app code keeps working.
import * as THREE from 'three';

const std = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: o.r ?? 0.75, metalness: o.m ?? 0, flatShading: !!o.flat, emissive: o.e ?? 0, emissiveIntensity: o.ei ?? 1 });

function capsule(r, len, mat, seg = 10) {
  const g = new THREE.CapsuleGeometry(r, Math.max(0.001, len - 2 * r), 6, seg);
  g.translate(0, -len / 2, 0);                     // hangs down from the joint
  const m = new THREE.Mesh(g, mat); m.castShadow = true; return m;
}
function sphere(r, mat, sx = 1, sy = 1, sz = 1) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 14), mat);
  m.scale.set(sx, sy, sz); m.castShadow = true; return m;
}
function at(m, x, y, z) { m.position.set(x, y, z); return m; }
function joint(parent, name, x, y, z, B) {
  const g = new THREE.Group(); g.name = name; g.position.set(x, y, z); parent.add(g); B[name] = g; return g;
}

/** spec: { height, bulk, skin, cloth, hair, armour?, kind: 'david'|'goliath' } */
export function buildHumanoid(spec) {
  const H = spec.height, k = spec.bulk ?? 1;
  const root = new THREE.Group(), B = {};
  const M = {
    skin: std(spec.skin, { r: 0.6 }), cloth: std(spec.cloth, { r: 0.9 }), cloth2: std(spec.cloth2 ?? spec.cloth, { r: 0.9 }),
    hair: std(spec.hair, { r: 0.95 }), dark: std(0x2a1d14), white: std(0xf8f6f0, { r: 0.3 }),
    eye: std(0x111111, { r: 0.2 }), metal: std(0xb98a45, { m: 0.85, r: 0.35 }), iron: std(0x6f7378, { m: 0.9, r: 0.35 }),
    leather: std(0x6b4423, { r: 0.85 }),
  };
  const hips = joint(root, 'hips', 0, 0.52 * H, 0, B);
  const spine = joint(hips, 'spine', 0, 0.02 * H, 0, B);
  const chest = joint(spine, 'chest', 0, 0.17 * H, 0, B);
  const neck = joint(chest, 'neck', 0, 0.14 * H, 0, B);
  const head = joint(neck, 'head', 0, 0.06 * H, 0, B);

  // torso
  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.105 * H * k, 0.085 * H * k, 0.33 * H, 18), spec.armour ? M.metal : M.cloth);
  torso.scale.z = 0.62; torso.position.y = 0.15 * H; torso.castShadow = true; spine.add(torso);
  // skirt / tunic hem on the hips
  const skirt = new THREE.Mesh(new THREE.CylinderGeometry(0.088 * H * k, 0.12 * H * k, 0.2 * H, 18, 1, true), spec.armour ? M.leather : M.cloth2);
  skirt.material.side = THREE.DoubleSide; skirt.scale.z = 0.7; skirt.position.y = -0.08 * H; skirt.castShadow = true; hips.add(skirt);
  const belt = new THREE.Mesh(new THREE.TorusGeometry(0.09 * H * k, 0.012 * H, 6, 24), M.leather);
  belt.rotation.x = Math.PI / 2; belt.scale.y = 0.62; belt.position.y = 0.01 * H; hips.add(belt);

  // head + face
  const R = 0.085 * H;
  head.add(at(sphere(R, M.skin, 0.92, 1.08, 1), 0, R, 0));
  const face = new THREE.Group(); face.position.set(0, R, R * 0.85); head.add(face);
  for (const s of [-1, 1]) {
    const w = sphere(R * 0.2, M.white, 1, 0.8, 0.5); w.position.set(s * R * 0.36, R * 0.12, 0); face.add(w);
    const p = sphere(R * 0.1, M.eye, 1, 1, 0.5); p.position.set(s * R * 0.36, R * 0.12, R * 0.08); face.add(p);
    const brow = new THREE.Mesh(new THREE.BoxGeometry(R * 0.38, R * 0.07, R * 0.08), M.hair);
    brow.position.set(s * R * 0.36, R * 0.36, R * 0.02); brow.rotation.z = s * (spec.kind === 'goliath' ? 0.45 : -0.1); face.add(brow);
  }
  const nose = sphere(R * 0.12, M.skin, 0.8, 1.2, 1); nose.position.set(0, -R * 0.08, R * 0.1); face.add(nose);
  const mouth = new THREE.Mesh(new THREE.BoxGeometry(R * 0.36, R * 0.06, R * 0.05), M.dark);
  mouth.position.set(0, -R * 0.42, 0); face.add(mouth); B.mouth = mouth;

  if (spec.kind === 'goliath') {
    const beard = new THREE.Mesh(new THREE.ConeGeometry(R * 0.7, R * 1.1, 14), M.hair);
    beard.rotation.x = Math.PI; beard.position.set(0, -R * 0.7, -R * 0.25); face.add(beard);
    const helm = new THREE.Mesh(new THREE.SphereGeometry(R * 1.12, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.55), M.metal);
    helm.position.y = R * 1.05; head.add(helm);
    const crest = new THREE.Mesh(new THREE.BoxGeometry(R * 0.18, R * 0.6, R * 1.9), std(0xa3242b));
    crest.position.set(0, R * 2.2, -R * 0.1); head.add(crest);
    const guard = new THREE.Mesh(new THREE.BoxGeometry(R * 0.14, R * 0.7, R * 0.12), M.metal);
    guard.position.set(0, R * 0.95, R * 1.08); head.add(guard);
    // shoulder pauldrons
    for (const s of [-1, 1]) { const pd = sphere(0.075 * H, M.metal, 1.2, 0.8, 1); pd.position.set(s * 0.13 * H * k, 0.12 * H, 0); chest.add(pd); }
  } else {
    for (let i = 0; i < 14; i++) {
      const a = (i / 14) * Math.PI * 2, c = sphere(R * 0.32, M.hair);
      c.position.set(Math.cos(a) * R * 0.78, R * 1.35 + Math.sin(i * 1.7) * R * 0.15, Math.sin(a) * R * 0.7 - R * 0.1); head.add(c);
    }
  }

  // arms
  for (const s of [-1, 1]) {
    const side = s < 0 ? 'L' : 'R';
    const sh = joint(chest, 'shoulder' + side, s * 0.125 * H * k, 0.11 * H, 0, B);
    sh.add(capsule(0.032 * H * k, 0.17 * H, spec.armour ? M.skin : M.cloth));
    const el = joint(sh, 'elbow' + side, 0, -0.17 * H, 0, B);
    el.add(capsule(0.027 * H * k, 0.16 * H, M.skin));
    if (spec.armour) { const br = capsule(0.032 * H * k, 0.1 * H, M.metal); br.position.y = -0.03 * H; el.add(br); }
    const hd = joint(el, 'hand' + side, 0, -0.16 * H, 0, B);
    hd.add(at(sphere(0.03 * H * k, M.skin, 0.9, 1.2, 0.7), 0, -0.025 * H, 0));
  }
  // legs
  for (const s of [-1, 1]) {
    const side = s < 0 ? 'L' : 'R';
    const hp = joint(hips, 'hip' + side, s * 0.055 * H * k, -0.02 * H, 0, B);
    hp.add(capsule(0.042 * H * k, 0.25 * H, M.skin));
    const kn = joint(hp, 'knee' + side, 0, -0.25 * H, 0, B);
    kn.add(capsule(0.034 * H * k, 0.23 * H, M.skin));
    if (spec.armour) { const gr = capsule(0.04 * H * k, 0.17 * H, M.metal); gr.position.y = -0.02 * H; kn.add(gr); }
    const ft = joint(kn, 'foot' + side, 0, -0.23 * H, 0, B);
    const sole = new THREE.Mesh(new THREE.BoxGeometry(0.06 * H * k, 0.025 * H, 0.12 * H), M.leather);
    sole.position.set(0, 0.0, 0.03 * H); sole.castShadow = true; ft.add(sole);
  }

  const self = { root, B, M, H, kind: spec.kind };
  if (spec.kind === 'goliath') addGoliathGear(self); else addDavidGear(self);
  return self;
}

function addGoliathGear(c) {
  const { B, H, M } = c;
  // spear in the right hand, shield on the left forearm
  const spear = new THREE.Group(); B.handR.add(spear); spear.position.y = -0.03 * H; c.spear = spear;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.012 * H, 0.012 * H, 1.25 * H, 8), M.leather);
  shaft.rotation.x = Math.PI / 2; shaft.position.z = 0.2 * H; shaft.castShadow = true; spear.add(shaft);
  const tip = new THREE.Mesh(new THREE.ConeGeometry(0.03 * H, 0.16 * H, 4), M.iron);
  tip.rotation.x = Math.PI / 2; tip.position.z = 0.9 * H; spear.add(tip); c.spearTip = tip;
  const shield = new THREE.Mesh(new THREE.CylinderGeometry(0.17 * H, 0.17 * H, 0.025 * H, 28), M.metal);
  shield.rotation.z = Math.PI / 2; shield.position.set(-0.05 * H, -0.08 * H, 0.02 * H); shield.castShadow = true; B.elbowL.add(shield);
  const boss = new THREE.Mesh(new THREE.SphereGeometry(0.05 * H, 14, 10), M.iron); boss.position.set(-0.07 * H, -0.08 * H, 0.02 * H); B.elbowL.add(boss);
  c.shield = shield;
}

function addDavidGear(c) {
  const { B, H, M } = c;
  // sling: two cords from the right hand to a pouch holding the stone
  const sling = new THREE.Group(); B.handR.add(sling); sling.position.y = -0.05 * H; c.sling = sling;
  const cordMat = new THREE.MeshStandardMaterial({ color: 0xc9a36a, roughness: 0.9 });
  const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.004 * H, 0.004 * H, 0.3 * H, 5), cordMat);
  cord.position.y = -0.15 * H; sling.add(cord);
  const pouch = new THREE.Mesh(new THREE.SphereGeometry(0.03 * H, 10, 8), M.leather); pouch.position.y = -0.3 * H; sling.add(pouch);
  const stone = new THREE.Mesh(new THREE.SphereGeometry(0.022 * H, 10, 8), new THREE.MeshStandardMaterial({ color: 0xd8d2c4, emissive: 0xffd27a, emissiveIntensity: 0 }));
  stone.position.y = -0.3 * H; sling.add(stone); c.stone = stone;
  const bag = new THREE.Mesh(new THREE.BoxGeometry(0.09 * H, 0.1 * H, 0.05 * H), M.leather);
  bag.position.set(0.11 * H, -0.06 * H, 0.04 * H); B.hips.add(bag);
}

// ---------------- poses ----------------
const sin = Math.sin;
export function resetPose(c) {
  for (const n of ['spine', 'chest', 'neck', 'head', 'shoulderL', 'shoulderR', 'elbowL', 'elbowR', 'handL', 'handR', 'hipL', 'hipR', 'kneeL', 'kneeR', 'footL', 'footR'])
    c.B[n].rotation.set(0, 0, 0);
  c.B.hips.position.y = 0.52 * c.H; c.B.hips.rotation.set(0, 0, 0);
  c.B.shoulderL.rotation.z = -0.12; c.B.shoulderR.rotation.z = 0.12;
}
export function idle(c, t, amt = 1) {
  c.B.chest.rotation.x += 0.03 * sin(t * 1.6) * amt;
  c.B.head.rotation.y += 0.1 * sin(t * 0.7) * amt;
  c.B.elbowL.rotation.x -= 0.15 * amt; c.B.elbowR.rotation.x -= 0.15 * amt;
}
/** walk/run cycle; phase in radians, amt 0..1, run boosts amplitude */
export function walk(c, phase, amt = 1, run = 0) {
  const A = (0.45 + 0.35 * run) * amt, B = c.B;
  B.hipL.rotation.x = -A * sin(phase); B.hipR.rotation.x = A * sin(phase);
  B.kneeL.rotation.x = Math.max(0, sin(phase - 1.2)) * (0.7 + run * 0.6) * amt;
  B.kneeR.rotation.x = Math.max(0, -sin(phase - 1.2)) * (0.7 + run * 0.6) * amt;
  B.shoulderL.rotation.x = A * 0.8 * sin(phase); B.shoulderR.rotation.x = -A * 0.8 * sin(phase);
  B.hips.position.y = 0.52 * c.H - Math.abs(sin(phase)) * 0.02 * c.H * amt + 0.02 * c.H * run * amt;
  B.spine.rotation.x = -0.12 * run * amt;
}
export function setMouth(c, open) { c.B.mouth.scale.y = 1 + open * 4; }
