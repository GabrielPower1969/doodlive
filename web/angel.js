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
  m.userData.uniforms = { uBase: { value: new THREE.Color(base) }, uBaseAmt: { value: opts.baseAmt ?? 0.9 }, uRim: { value: opts.rim ?? 0.25 }, uInk: { value: opts.ink ?? 0 } };
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, m.userData.uniforms);
    sh.fragmentShader = 'uniform vec3 uBase; uniform float uBaseAmt; uniform float uRim; uniform float uInk;\n' + sh.fragmentShader
      .replace('#include <map_fragment>', `#include <map_fragment>
        // unpainted paper (near white) -> part's default colour; crayon colour wins where painted
        float paper = smoothstep(0.60, 0.86, min(min(diffuseColor.r, diffuseColor.g), diffuseColor.b));
        // where the 3D model has real features (face), drawn ink lines would double them: hide the ink
        float ink = 1.0 - smoothstep(0.08, 0.35, max(max(diffuseColor.r, diffuseColor.g), diffuseColor.b));
        diffuseColor.rgb = mix(diffuseColor.rgb, uBase, max(paper * uBaseAmt, ink * uInk));`)
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
    hair: makeMaterial(tex, 0x8a5a32, { roughness: 0.9, rim: 0.2, ink: 1 }),
    face: makeMaterial(tex, 0xf3cdb4, { baseAmt: 0.95, roughness: 0.6, rim: 0.15, ink: 1 }),
    wing: makeMaterial(tex, 0xf7f5ef, { side: THREE.DoubleSide, rim: 0.4 }),
    // (vertex colours on the wing give each feather its own shade)
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

  // --- head: skull + sculpted face (positions measured on lineart.png) + curls ---
  const HC = P(525, 358, 0), HRX = PX(76), HRY = PX(88), HRZ = PX(82);
  attach(ellipsoid(HC, HRX, HRY, HRZ, 48, 36), M.face, B.head);
  const surfZ = (x, y) => { const p = P(x, y), dx = (p.x - HC.x) / HRX, dy = (p.y - HC.y) / HRY; return HC.z + HRZ * Math.sqrt(Math.max(0, 1 - dx * dx - dy * dy)); };
  const on = (x, y, out = 0) => P(x, y, surfZ(x, y) + out);
  const local = (obj, p, b) => { obj.position.copy(p).sub(b.userData.rest); b.add(obj); return obj; };
  const FM = {
    white: new THREE.MeshStandardMaterial({ color: 0xfbfaf6, roughness: 0.2 }),
    iris: new THREE.MeshStandardMaterial({ color: 0x4f86b8, roughness: 0.25, emissive: 0x10263a, emissiveIntensity: 0.4 }),
    pupil: new THREE.MeshStandardMaterial({ color: 0x07070b, roughness: 0.15 }),
    shine: new THREE.MeshBasicMaterial({ color: 0xffffff }),
    lash: new THREE.MeshStandardMaterial({ color: 0x2b1a10, roughness: 0.6 }),
    brow: new THREE.MeshStandardMaterial({ color: 0x7a4e2a, roughness: 0.9 }),
    lip: new THREE.MeshStandardMaterial({ color: 0xd8807e, roughness: 0.4 }),
    mouth: new THREE.MeshStandardMaterial({ color: 0x5a1c24, roughness: 0.9 }),
    blush: new THREE.MeshBasicMaterial({ map: radialTexture('rgba(255,120,140,0.55)'), transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 }),
  };
  const face = { lids: [], eyes: [] };
  const ER = PX(13);
  for (const [x, y] of [[472, 333], [547, 313]]) {
    const eye = local(new THREE.Group(), on(x, y, -ER * 0.62), B.head);
    const ball = new THREE.Group(); eye.add(ball); face.eyes.push(ball);
    ball.add(new THREE.Mesh(new THREE.SphereGeometry(ER, 24, 16), FM.white));
    const iris = new THREE.Mesh(new THREE.SphereGeometry(ER * 0.56, 20, 12), FM.iris); iris.scale.z = 0.45; iris.position.z = ER * 0.8; ball.add(iris);
    const pupil = new THREE.Mesh(new THREE.SphereGeometry(ER * 0.27, 16, 10), FM.pupil); pupil.scale.z = 0.4; pupil.position.z = ER * 0.92; ball.add(pupil);
    const shine = new THREE.Mesh(new THREE.SphereGeometry(ER * 0.11, 8, 6), FM.shine); shine.position.set(ER * 0.22, ER * 0.24, ER * 0.98); ball.add(shine);
    const lid = new THREE.Group(); eye.add(lid); face.lids.push(lid);
    lid.add(new THREE.Mesh(new THREE.SphereGeometry(ER * 1.1, 24, 12, 0, Math.PI * 2, 0, Math.PI * 0.5), M.face));
    const lash = new THREE.Mesh(new THREE.TorusGeometry(ER * 1.12, ER * 0.13, 6, 24, Math.PI), FM.lash); lash.rotation.x = Math.PI / 2; lid.add(lash);
    const lower = new THREE.Mesh(new THREE.SphereGeometry(ER * 1.06, 24, 8, 0, Math.PI * 2, Math.PI * 0.68, Math.PI * 0.32), M.face); eye.add(lower);
  }
  for (const pts of [[[448, 318], [462, 308], [480, 303], [496, 308]], [[512, 297], [528, 288], [546, 285], [563, 291]]]) {
    const curve = new THREE.CatmullRomCurve3(pts.map(([x, y]) => on(x, y, PX(2.5))));
    attach(new THREE.TubeGeometry(curve, 16, PX(3.4), 6, false), FM.brow, B.head);
  }
  attach(ellipsoid(on(519, 360, -PX(6)), PX(10), PX(24), PX(12)), M.face, B.head);   // nose bridge
  attach(ellipsoid(on(517, 378, -PX(2)), PX(10), PX(8), PX(8)), M.face, B.head);     // nose tip
  // mouth: upper lip tube (smile), lower lip on a "jaw" that opens while talking, dark inside
  const mouth = local(new THREE.Group(), on(527, 402, -PX(3)), B.head);
  const upper = new THREE.CatmullRomCurve3([[-24, 1], [-12, 3.5], [0, 2], [12, 3.5], [24, 1]].map(([x, y]) => new THREE.Vector3(PX(x), PX(y), PX(Math.abs(x) < 15 ? 2 : -2))));
  mouth.add(new THREE.Mesh(new THREE.TubeGeometry(upper, 20, PX(3.2), 8, false), FM.lip));
  const mouthIn = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 8), FM.mouth); mouthIn.scale.set(PX(19), PX(3), PX(3)); mouthIn.position.set(0, -PX(2), -PX(1)); mouth.add(mouthIn);
  const jaw = new THREE.Group(); mouth.add(jaw);
  const lowLip = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 10), FM.lip); lowLip.scale.set(PX(17), PX(5), PX(5)); lowLip.position.set(0, -PX(6), PX(1)); jaw.add(lowLip);
  Object.assign(face, { jaw, mouthIn });
  for (const [x, y, ry] of [[470, 368, -0.45], [566, 350, 0.45]]) {
    const b = local(new THREE.Mesh(new THREE.CircleGeometry(PX(20), 24), FM.blush), on(x, y, PX(1.5)), B.head); b.rotation.y = ry;
  }
  // hair: back volume + rings of curls following the drawn hair outline + fringe
  attach(ellipsoid(P(533, 330, -0.035), PX(124), PX(138), PX(86)), M.hair, B.head);
  const rnd = mulberry(11);
  for (let k = 0; k < 2; k++) {
    const rx = PX(92 + k * 26), ry = PX(100 + k * 28), n = 17 + k * 4;
    for (let i = 0; i < n; i++) {
      const a = THREE.MathUtils.degToRad(-55 + (290 * i) / (n - 1)) + (rnd() - 0.5) * 0.08;
      const c = new THREE.Vector3(P(533, 0).x + Math.cos(a) * rx, P(0, 340).y + Math.sin(a) * ry, 0);
      const fx = (c.x - HC.x) / (HRX * 1.02), fy = (c.y - HC.y) / (HRY * 1.02);
      if (fx * fx + fy * fy < 1 && c.y < HC.y + HRY * 0.55) continue;          // keep the face clear
      c.z = 0.03 - k * 0.028 + (rnd() - 0.5) * 0.01;
      const r = PX(20 + rnd() * 10 - k * 2);
      attach(ellipsoid(c, r, r * 1.05, r * 0.9, 14, 10), M.hair, B.head);
    }
  }
  for (const x of [476, 500, 524, 548, 572]) attach(ellipsoid(on(x, 274 + Math.abs(x - 524) * 0.25, -PX(4)), PX(19), PX(15), PX(14), 14, 10), M.hair, B.head);

  // --- arms (wide sleeves + skin forearms) ---
  attach(limb(P(350, 600), P(285, 840), PX(62), PX(78)), M.robe, B.shoulderL);
  attach(limb(P(285, 830), P(180, 975), PX(30), PX(24)), M.skin, B.elbowL);
  attach(ellipsoid(P(140, 1010, 0.01), PX(55), PX(35), PX(18)), M.skin, B.wristL);
  attach(limb(P(760, 610), P(840, 850), PX(62), PX(78)), M.robe, B.shoulderR);
  attach(limb(P(840, 840), P(972, 1018), PX(30), PX(24)), M.skin, B.elbowR);
  attach(ellipsoid(P(984, 1034, 0.01), PX(30), PX(42), PX(30)), M.skin, B.wristR);

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
    const slab = tessellate(g, 0.03);
    slab.translate(0, 0, -0.072);
    const tg = mergeGeoms([slab, featherCover(wingOutline, side)]);
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
    M.wing.vertexColors = true;
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
  const crnd = mulberry(7);
  for (let i = 0; i < 22; i++) {
    const a = crnd() * Math.PI * 2, r = 0.1 + crnd() * 0.32;
    const s = 0.05 + crnd() * 0.06;
    const m = new THREE.Mesh(new THREE.SphereGeometry(s, 16, 12), cloudMat);
    m.position.set(Math.cos(a) * r * 1.2, -0.03 + crnd() * 0.04, Math.sin(a) * r * 0.6);
    cloud.add(m);
  }
  root.add(cloud);

  return { root, rig, bones: B, meshes, materials: M, halo, glow, cloud, wings: wingMeshes, face, talking: false };
}

// Feathers radiating from the wing root, filling the drawn wing outline. Model space, rest pose.
function featherCover(outline, side) {
  const root = [430, 560];
  const inside = (x, y) => { let c = false; for (let i = 0, j = outline.length - 1; i < outline.length; j = i++) {
    const [xi, yi] = outline[i], [xj, yj] = outline[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c; } return c; };
  const rnd = mulberry(side === 'L' ? 3 : 5);
  const pos = [], col = [], idx = [];
  const STEP = 24;
  for (let y = 0; y < 820; y += STEP) for (let x = 0; x < 450; x += STEP) {
    const bx = x + (rnd() - 0.5) * STEP * 0.6, by = y + (rnd() - 0.5) * STEP * 0.6;
    if (!inside(bx, by)) continue;
    const dx = bx - root[0], dy = by - root[1], d = Math.hypot(dx, dy) || 1;
    const ux = dx / d, uy = dy / d;
    let L = Math.min(210, 46 + 0.38 * d);
    while (L > 30 && !inside(bx + ux * L * 0.8, by + uy * L * 0.8)) L *= 0.85;
    const W = L * (0.24 + rnd() * 0.06), seg = 6, shade = 0.86 + rnd() * 0.14;
    const z = -0.052 - d * 0.000035 + (rnd() - 0.5) * 0.002;
    const base = pos.length / 3;
    for (let i = 0; i <= seg; i++) {
      const t = i / seg, w = W * Math.sin(Math.PI * Math.pow(t, 0.6)) * (1 - 0.3 * t);
      const cx = bx + ux * L * t, cy = by + uy * L * t, zz = z + 0.012 * t * t;   // tips curl back
      for (const [o, lift] of [[-1, 0], [0, 0.004], [1, 0]]) {
        const px = cx - uy * w * o, py = cy + ux * w * o;
        const v = side === 'L' ? P(px, py, zz + lift) : P(AW - px, py, zz + lift);
        pos.push(v.x, v.y, v.z);
        const k = shade * (o === 0 ? 1.04 : 1) * (1 - 0.12 * t);
        col.push(k, k, k);
      }
    }
    for (let i = 0; i < seg; i++) for (let c = 0; c < 2; c++) { const a = base + i * 3 + c, b = a + 3; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx); g.computeVertexNormals();
  return g;
}

function mergeGeoms(list) {
  const pos = [], col = [], nor = [], idx = [];
  for (const g0 of list) {
    const g = g0.index ? g0 : g0.toNonIndexed();
    const base = pos.length / 3, p = g.attributes.position, n = g.attributes.normal, c = g.attributes.color;
    for (let i = 0; i < p.count; i++) {
      pos.push(p.getX(i), p.getY(i), p.getZ(i)); nor.push(n.getX(i), n.getY(i), n.getZ(i));
      if (c) col.push(c.getX(i), c.getY(i), c.getZ(i)); else col.push(0.97, 0.97, 0.97);
    }
    if (g.index) for (const i of g.index.array) idx.push(base + i); else for (let i = 0; i < p.count; i++) idx.push(base + i);
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  out.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  out.setIndex(idx);
  return out;
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

  // face: blink every ~4 s, wide eyes during the fanfare, mouth flaps while the voice plays
  const bt = (time + 0.7) % 4.2, blink = bt < 0.14 ? Math.sin((bt / 0.14) * Math.PI) : 0;
  const wide = state.phase === 'action' ? 0.25 : 0;
  for (const lid of angel.face.lids) lid.rotation.x = THREE.MathUtils.lerp(-0.55 - wide, 1.5, blink);
  for (const e of angel.face.eyes) e.rotation.set(0.05 * s(time * 0.37), 0.12 * s(time * 0.29), 0);
  const talk = angel.talking ? 0.3 + 0.7 * Math.abs(s(time * 13) * s(time * 5.3 + 1)) : 0;
  angel.face.jaw.position.y = -PX(6) * talk;
  angel.face.mouthIn.scale.y = PX(3 + 9 * talk);

  angel.halo.rotation.z = time * 0.6;
  angel.glow.material.opacity = 0.6 + 0.25 * s(time * 2);
  angel.cloud.rotation.y = time * 0.1;
  angel.cloud.position.y = -0.02 * s(time * 0.8);
}
