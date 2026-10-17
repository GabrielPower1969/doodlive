// Procedural, rigged 3D angel built to line up with the colouring page, so the scanned page can be
// front-projected onto it (UV = position on the page). Replace with a Blender GLB later: keep the
// same bone names and the same "UV = page position" rule and app.js does not change.
import * as THREE from 'three';

// Line-art pixel space (web/assets/lineart.png is 1128 x 1384). Model units: 1 = art width.
const AW = 1128, AH = 1384, ASPECT = AH / AW;
const P = (x, y, z = 0) => new THREE.Vector3((x - AW / 2) / AW, (AH - y) / AW, z);
const PX = px => px / AW;

function frontUV(geom) {
  const pos = geom.attributes.position, uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {
    uv[i * 2] = pos.getX(i) + 0.5;
    uv[i * 2 + 1] = pos.getY(i) / ASPECT;
  }
  geom.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return geom;
}

/** Ellipse-section tube through rings {y, cx, rx, rz, cz, folds}. Open bottom, capped top. */
function loft(rings, seg = 48) {
  const pos = [], idx = [];
  rings.forEach(r => {
    for (let s = 0; s <= seg; s++) {
      const a = (s / seg) * Math.PI * 2;
      const fold = r.folds ? 1 + r.folds * Math.sin(a * 11) * Math.max(0, Math.cos(a - Math.PI / 2) * 0.5 + 0.5) : 1;
      pos.push(r.cx + Math.cos(a) * r.rx * fold, r.y, (r.cz || 0) + Math.sin(a) * r.rz * fold);
    }
  });
  for (let i = 0; i < rings.length - 1; i++) for (let s = 0; s < seg; s++) {
    const a = i * (seg + 1) + s, b = a + seg + 1;
    idx.push(a, b, a + 1, b, b + 1, a + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** Capsule-ish limb between two model-space points. */
function limb(a, b, r0, r1) {
  const dir = new THREE.Vector3().subVectors(b, a), L = dir.length();
  const g = new THREE.CylinderGeometry(r1, r0, L, 20, 4, false);
  g.translate(0, L / 2, 0);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize()));
  g.translate(a.x, a.y, a.z);
  return g;
}

function ellipsoid(c, rx, ry, rz, ws = 32, hs = 24) {
  const g = new THREE.SphereGeometry(1, ws, hs);
  g.scale(rx, ry, rz); g.translate(c.x, c.y, c.z);
  return g;
}

function makeMaterial(tex, base, opts = {}) {
  const m = new THREE.MeshStandardMaterial({ map: tex, roughness: opts.roughness ?? 0.75, metalness: opts.metalness ?? 0, side: opts.side ?? THREE.FrontSide });
  m.userData.uniforms = { uBase: { value: new THREE.Color(base) }, uBaseAmt: { value: opts.baseAmt ?? 0.9 }, uRim: { value: opts.rim ?? 0.25 } };
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, m.userData.uniforms);
    sh.fragmentShader = 'uniform vec3 uBase; uniform float uBaseAmt; uniform float uRim;\n' + sh.fragmentShader
      .replace('#include <map_fragment>', `#include <map_fragment>
        // unpainted paper (near white) -> part's default colour; crayon colour wins where painted
        float paper = smoothstep(0.60, 0.86, min(min(diffuseColor.r, diffuseColor.g), diffuseColor.b));
        diffuseColor.rgb = mix(diffuseColor.rgb, uBase, paper * uBaseAmt);`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        float rim = 1.0 - abs(dot(normal, normalize(vViewPosition)));
        totalEmissiveRadiance += uRim * pow(rim, 3.0) * vec3(1.0, 0.95, 0.8);`);
  };
  return m;
}

export function buildAngel(texture) {
  const root = new THREE.Group(); root.name = 'angel';
  const rig = new THREE.Group(); root.add(rig);           // float/bob offset lives here
  const B = {};
  const bone = (name, at, parent) => {
    const b = new THREE.Bone(); b.name = name; b.userData.rest = at.clone();
    const pp = parent ? parent.userData.rest : new THREE.Vector3();
    b.position.copy(at).sub(pp);
    (parent || rig).add(b); B[name] = b; return b;
  };
  // Skeleton (rest pose = drawing pose)
  bone('hips', P(565, 930), null);
  bone('spine', P(560, 640), B.hips);
  bone('neck', P(535, 500), B.spine);
  bone('head', P(527, 420), B.neck);
  bone('shoulderL', P(350, 610), B.spine);
  bone('elbowL', P(285, 830), B.shoulderL);
  bone('wristL', P(175, 975), B.elbowL);
  bone('shoulderR', P(760, 620), B.spine);
  bone('elbowR', P(840, 840), B.shoulderR);
  bone('wristR', P(955, 1010), B.elbowR);
  bone('wingL', P(420, 560, -0.06), B.spine);
  bone('wingLmid', P(210, 330, -0.06), B.wingL);
  bone('wingLtip', P(20, 30, -0.06), B.wingLmid);
  bone('wingR', P(708, 560, -0.06), B.spine);
  bone('wingRmid', P(918, 330, -0.06), B.wingR);
  bone('wingRtip', P(1108, 30, -0.06), B.wingRmid);

  const tex = texture;
  const M = {
    robe: makeMaterial(tex, 0xf4f4f8, { rim: 0.35 }),
    skin: makeMaterial(tex, 0xf3cdb4, { baseAmt: 0.95, roughness: 0.6, rim: 0.15 }),
    hair: makeMaterial(tex, 0x8a5a32, { roughness: 0.9, rim: 0.2 }),
    wing: makeMaterial(tex, 0xf7f5ef, { side: THREE.DoubleSide, rim: 0.4 }),
    gold: makeMaterial(tex, 0xd9a43a, { metalness: 0.85, roughness: 0.3, rim: 0.3 }),
  };
  const meshes = [];
  const attach = (geom, mat, b) => {
    frontUV(geom);
    const r = b ? b.userData.rest : new THREE.Vector3();
    geom.translate(-r.x, -r.y, -r.z);
    const m = new THREE.Mesh(geom, mat); m.castShadow = true;
    (b || rig).add(m); meshes.push(m); return m;
  };

  // --- body ---
  const D = 0.55; // depth/width ratio of the robe
  attach(loft([
    { y: P(0, 1384).y - 0.02, cx: PX(550 - 564), rx: PX(285), rz: PX(285) * D, folds: 0.05 },
    { y: P(0, 1250).y, cx: PX(555 - 564), rx: PX(255), rz: PX(255) * D, folds: 0.045 },
    { y: P(0, 1100).y, cx: PX(560 - 564), rx: PX(220), rz: PX(220) * D, folds: 0.03 },
    { y: P(0, 950).y, cx: PX(565 - 564), rx: PX(185), rz: PX(185) * D, folds: 0.01 },
    { y: P(0, 930).y, cx: PX(565 - 564), rx: PX(178), rz: PX(178) * D },
  ]), M.robe, B.hips);
  attach(loft([
    { y: P(0, 945).y, cx: PX(565 - 564), rx: PX(190), rz: PX(190) * D },
    { y: P(0, 915).y, cx: PX(565 - 564), rx: PX(190), rz: PX(190) * D },
  ], 40), M.robe, B.hips); // belt
  attach(loft([
    { y: P(0, 935).y, cx: PX(565 - 564), rx: PX(178), rz: PX(178) * D },
    { y: P(0, 800).y, cx: PX(563 - 564), rx: PX(200), rz: PX(200) * D * 0.95 },
    { y: P(0, 640).y, cx: PX(560 - 564), rx: PX(205), rz: PX(205) * D * 0.85 },
    { y: P(0, 545).y, cx: PX(555 - 564), rx: PX(175), rz: PX(175) * D * 0.75 },
    { y: P(0, 505).y, cx: PX(545 - 564), rx: PX(90), rz: PX(90) * 0.8 },
    { y: P(0, 500).y, cx: PX(545 - 564), rx: PX(1), rz: PX(1) },
  ]), M.robe, B.spine);
  attach(limb(P(537, 520), P(532, 440), PX(32), PX(30)), M.skin, B.neck);

  // --- head ---
  attach(ellipsoid(P(522, 330, 0.03), PX(66), PX(92), PX(70)), M.skin, B.head);
  attach(ellipsoid(P(522, 312, 0.075), PX(10), PX(18), PX(12), 12, 8), M.skin, B.head); // nose
  attach(ellipsoid(P(535, 300, -0.02), PX(140), PX(150), PX(105)), M.hair, B.head);
  attach(ellipsoid(P(535, 225, 0.0), PX(120), PX(70), PX(95)), M.hair, B.head);

  // --- arms (wide sleeves + skin forearms) ---
  attach(limb(P(350, 600), P(285, 840), PX(62), PX(78)), M.robe, B.shoulderL);
  attach(limb(P(285, 830), P(180, 975), PX(30), PX(24)), M.skin, B.elbowL);
  attach(ellipsoid(P(140, 1010, 0.01), PX(55), PX(35), PX(18)), M.skin, B.wristL);
  attach(limb(P(760, 610), P(840, 850), PX(62), PX(78)), M.robe, B.shoulderR);
  attach(limb(P(840, 840), P(950, 1005), PX(30), PX(24)), M.skin, B.elbowR);
  attach(ellipsoid(P(965, 1035, 0.01), PX(32), PX(45), PX(30)), M.skin, B.wristR);

  // --- trumpet in the right hand ---
  attach(limb(P(940, 1300), P(1072, 540), PX(9), PX(5)), M.gold, B.wristR);
  {
    const a = P(945, 1270), b = P(905, 1355);
    const g = limb(a, b, PX(12), PX(60));
    attach(g, M.gold, B.wristR);
  }

  // --- wings: skinned to a 3-bone chain each ---
  const wingOutline = [[20, 30], [130, 95], [240, 200], [330, 330], [390, 450], [430, 560], [410, 650], [340, 740], [250, 800],
    [170, 770], [90, 710], [15, 650], [0, 430], [30, 330], [80, 250], [40, 120]];
  const wingMeshes = [];
  for (const side of ['L', 'R']) {
    const pts = wingOutline.map(([x, y]) => (side === 'L' ? P(x, y) : P(AW - x, y)));
    const shape = new THREE.Shape(pts.map(p => new THREE.Vector2(p.x, p.y)));
    const g = new THREE.ExtrudeGeometry(shape, { depth: 0.012, bevelEnabled: true, bevelThickness: 0.008, bevelSize: 0.006, bevelSegments: 2, curveSegments: 4, steps: 1 });
    // densify for smooth skinning: tessellate along the wing
    const tg = tessellate(g, 0.03);
    tg.translate(0, 0, -0.066);
    frontUV(tg);
    const chain = [B['wing' + side], B['wing' + side + 'mid'], B['wing' + side + 'tip']];
    const r0 = chain[0].userData.rest, r2 = chain[2].userData.rest;
    const axis = new THREE.Vector3().subVectors(r2, r0), L2 = axis.lengthSq();
    const pos = tg.attributes.position, si = [], sw = [], v = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      const s = THREE.MathUtils.clamp(v.clone().sub(r0).dot(axis) / L2, 0, 1);
      if (s < 0.5) { const w = s / 0.5; si.push(0, 1, 0, 0); sw.push(1 - w, w, 0, 0); }
      else { const w = (s - 0.5) / 0.5; si.push(1, 2, 0, 0); sw.push(1 - w, w, 0, 0); }
    }
    tg.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(si, 4));
    tg.setAttribute('skinWeight', new THREE.Float32BufferAttribute(sw, 4));
    const sm = new THREE.SkinnedMesh(tg, M.wing); sm.castShadow = true; sm.frustumCulled = false;
    rig.add(sm); meshes.push(sm);
    wingMeshes.push({ mesh: sm, chain });
  }
  root.updateMatrixWorld(true);
  for (const w of wingMeshes) w.mesh.bind(new THREE.Skeleton(w.chain), w.mesh.matrixWorld);

  // --- halo + glow + cloud ---
  const halo = new THREE.Mesh(new THREE.TorusGeometry(0.115, 0.009, 12, 64),
    new THREE.MeshBasicMaterial({ color: 0xffe9a0, transparent: true, opacity: 0.95 }));
  halo.position.copy(P(527, 175, -0.04)).sub(B.head.userData.rest);
  halo.rotation.x = -1.15;
  B.head.add(halo);
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: radialTexture('rgba(255,240,190,0.85)'), depthWrite: false, transparent: true, blending: THREE.AdditiveBlending }));
  glow.scale.set(0.55, 0.55, 1); glow.position.copy(P(527, 300, -0.15)).sub(B.head.userData.rest);
  B.head.add(glow);

  const cloud = new THREE.Group();
  const cloudMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 1, transparent: true, opacity: 0.92, emissive: 0x8899aa, emissiveIntensity: 0.25 });
  const rnd = mulberry(7);
  for (let i = 0; i < 22; i++) {
    const a = rnd() * Math.PI * 2, r = 0.1 + rnd() * 0.32;
    const s = 0.05 + rnd() * 0.06;
    const m = new THREE.Mesh(new THREE.SphereGeometry(s, 16, 12), cloudMat);
    m.position.set(Math.cos(a) * r * 1.2, -0.03 + rnd() * 0.04, Math.sin(a) * r * 0.6);
    cloud.add(m);
  }
  root.add(cloud);

  return { root, rig, bones: B, meshes, materials: M, halo, glow, cloud, wings: wingMeshes };
}

// Split long triangles so the skinned wing bends smoothly.
function tessellate(geom, maxEdge) {
  const g = geom.index ? geom.toNonIndexed() : geom.clone();
  let pos = Array.from(g.attributes.position.array);
  for (let pass = 0; pass < 6; pass++) {
    const out = []; let split = false;
    for (let i = 0; i < pos.length; i += 9) {
      const a = pos.slice(i, i + 3), b = pos.slice(i + 3, i + 6), c = pos.slice(i + 6, i + 9);
      const e = [dist(a, b), dist(b, c), dist(c, a)], m = Math.max(...e);
      if (m <= maxEdge) { out.push(...a, ...b, ...c); continue; }
      split = true;
      if (m === e[0]) { const mid = lerp(a, b); out.push(...a, ...mid, ...c, ...mid, ...b, ...c); }
      else if (m === e[1]) { const mid = lerp(b, c); out.push(...a, ...b, ...mid, ...a, ...mid, ...c); }
      else { const mid = lerp(c, a); out.push(...a, ...b, ...mid, ...mid, ...b, ...c); }
    }
    pos = out; if (!split) break;
  }
  const ng = new THREE.BufferGeometry();
  ng.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  ng.computeVertexNormals();
  return ng;
}
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const lerp = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];

export function radialTexture(inner) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'), g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, inner); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function mulberry(a) { return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// ---------------- animation ----------------
const ease = t => t < 0 ? 0 : t > 1 ? 1 : t * t * (3 - 2 * t);
const easeOutBack = t => { const c = 1.7; t = Math.min(1, Math.max(0, t)); return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };

/** Pose the rig. state: {phase:'enter'|'idle'|'action', t: seconds in phase}, time: global seconds. */
export function animate(angel, state, time) {
  const B = angel.bones, s = Math.sin;
  let flapAmp = 0.12, flapSpeed = 1.6, armR = 0, elbowR = 0, armL = 0, elbowL = 0, headX = 0, headZ = 0, lift = 0;

  if (state.phase === 'enter') {
    const k = easeOutBack(state.t / 1.4);
    angel.root.scale.setScalar(Math.max(0.001, k));
    angel.rig.rotation.y = (1 - ease(state.t / 1.4)) * Math.PI * 2;
    lift = (1 - ease(state.t / 1.2)) * -0.25;
    flapAmp = 0.5; flapSpeed = 6;
  } else {
    angel.root.scale.setScalar(1);
    angel.rig.rotation.y = 0;
  }
  if (state.phase === 'action') {
    const t = state.t;
    const up = ease(t / 0.45) * (1 - ease((t - 2.6) / 0.6));
    armR = 1.05 * up; elbowR = -0.35 * up;
    armL = -0.75 * up + s(t * 7) * 0.12 * up; elbowL = 0.4 * up;
    headX = -0.22 * up; headZ = 0.12 * up;
    flapAmp = 0.12 + 0.45 * up; flapSpeed = 1.6 + 6 * up;
    lift = 0.05 * up + 0.01 * s(t * 20) * up;
  }

  // idle breathing / float
  angel.rig.position.y = lift + 0.018 * s(time * 1.3);
  B.spine.rotation.z = 0.02 * s(time * 0.9);
  B.head.rotation.set(headX + 0.04 * s(time * 0.7), 0.08 * s(time * 0.45), headZ + 0.03 * s(time * 0.8));
  B.shoulderR.rotation.z = armR + 0.03 * s(time * 1.1);
  B.elbowR.rotation.z = elbowR;
  B.shoulderL.rotation.z = armL - 0.03 * s(time * 1.1 + 1);
  B.elbowL.rotation.z = elbowL;

  const f = s(time * flapSpeed);
  const back = 0.3;
  B.wingL.rotation.set(0, -back - flapAmp * f, 0.05 * f);
  B.wingLmid.rotation.set(0, -0.08 - flapAmp * 0.6 * f, 0);
  B.wingLtip.rotation.set(0, -0.05 - flapAmp * 0.4 * f, 0);
  B.wingR.rotation.set(0, back + flapAmp * f, -0.05 * f);
  B.wingRmid.rotation.set(0, 0.08 + flapAmp * 0.6 * f, 0);
  B.wingRtip.rotation.set(0, 0.05 + flapAmp * 0.4 * f, 0);

  angel.halo.rotation.z = time * 0.6;
  angel.glow.material.opacity = 0.6 + 0.25 * s(time * 2);
  angel.cloud.rotation.y = time * 0.1;
  angel.cloud.position.y = -0.02 * s(time * 0.8);
}
