// Magic effects around the angel, in angel-model units (1 = art width, y up, feet at y=0).
// Everything is additive / no depth write, so it reads well over a camera feed.
import * as THREE from 'three';

function canvasTex(w, h, draw) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

const additive = (map, color = 0xffffff) => new THREE.MeshBasicMaterial({
  map, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, opacity: 0,
});

export function featherShape(len = 1, wid = 0.26, seg = 8) {
  // tapered vane along +y with a raised rachis; 3 columns: left edge, rachis, right edge
  const pos = [], idx = [];
  for (let i = 0; i <= seg; i++) {
    const t = i / seg, w = wid * Math.sin(Math.PI * Math.pow(t, 0.65)) * (1 - 0.25 * t);
    const bend = 0.12 * t * t;
    pos.push(-w, t * len, bend - 0.02 * w, 0, t * len, bend + 0.05 * wid, w, t * len, bend - 0.02 * w);
  }
  for (let i = 0; i < seg; i++) for (let c = 0; c < 2; c++) {
    const a = i * 3 + c, b = a + 3;
    idx.push(a, b, a + 1, b, b + 1, a + 1);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
  return g;
}

export function buildFx(parent) {
  const group = new THREE.Group(); parent.add(group);

  // light pillar
  const pillarTex = canvasTex(64, 256, (x, w, h) => {
    const g = x.createLinearGradient(0, h, 0, 0);
    g.addColorStop(0, 'rgba(255,240,190,0.9)'); g.addColorStop(0.5, 'rgba(255,230,170,0.35)'); g.addColorStop(1, 'rgba(255,230,170,0)');
    x.fillStyle = g; x.fillRect(0, 0, w, h);
  });
  const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.62, 2.6, 48, 1, true), additive(pillarTex, 0xfff0c8));
  pillar.position.y = 1.3; group.add(pillar);

  // magic circle on the ground
  const circleTex = canvasTex(512, 512, (x, w) => {
    const c = w / 2; x.translate(c, c); x.strokeStyle = 'rgba(255,220,140,1)'; x.fillStyle = 'rgba(255,220,140,1)';
    x.shadowColor = 'rgba(255,200,120,1)'; x.shadowBlur = 12;
    for (const [r, lw] of [[240, 5], [222, 2], [160, 3], [148, 1.5]]) { x.lineWidth = lw; x.beginPath(); x.arc(0, 0, r, 0, Math.PI * 2); x.stroke(); }
    x.lineWidth = 2.5; x.beginPath();
    for (let i = 0; i <= 7; i++) { const a = (i * 2 * 2 * Math.PI) / 7 - Math.PI / 2; x[i ? 'lineTo' : 'moveTo'](Math.cos(a) * 160, Math.sin(a) * 160); }
    x.stroke();
    for (let i = 0; i < 36; i++) { const a = (i / 36) * Math.PI * 2; x.save(); x.rotate(a); x.fillRect(-1.5, -238, 3, i % 3 ? 10 : 18); x.restore(); }
    for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; x.beginPath(); x.arc(Math.cos(a) * 192, Math.sin(a) * 192, i % 2 ? 6 : 10, 0, Math.PI * 2); x.fill(); }
  });
  const circle = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.5), additive(circleTex));
  circle.rotation.x = -Math.PI / 2; circle.position.y = 0.004; group.add(circle);

  // expanding burst ring
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.46, 0.5, 64), additive(null, 0xfff3c4));
  ring.rotation.x = -Math.PI / 2; ring.position.y = 0.01; group.add(ring);

  // falling feathers
  const fGeom = featherShape(0.11, 0.035);
  const fMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4dd, emissiveIntensity: 0.35, side: THREE.DoubleSide, transparent: true, depthWrite: false });
  const feathers = [];
  for (let i = 0; i < 18; i++) {
    const m = new THREE.Mesh(fGeom, fMat.clone()); m.visible = false; group.add(m);
    feathers.push({ m, t: 0, life: 0, x: 0, z: 0, y0: 0, spin: 0, phase: 0 });
  }

  let pillarAmt = 0, circleAmt = 0.35, ringT = 99, spawn = 0;
  const api = {
    group,
    trigger(kind) {
      if (kind === 'enter') { pillarAmt = 1; circleAmt = 1; ringT = 0; spawn = 14; }
      if (kind === 'action') { pillarAmt = 0.8; circleAmt = 1; ringT = 0; spawn = 10; }
    },
    update(dt, time) {
      pillarAmt = Math.max(0, pillarAmt - dt * 0.45);
      circleAmt = Math.max(0.35, circleAmt - dt * 0.3);
      pillar.material.opacity = pillarAmt * (0.75 + 0.25 * Math.sin(time * 9));
      pillar.rotation.y = time * 0.5;
      circle.material.opacity = circleAmt * (0.8 + 0.2 * Math.sin(time * 2.5));
      circle.rotation.z = time * 0.35;
      ringT += dt;
      const k = Math.min(1, ringT / 0.9);
      ring.scale.setScalar(0.2 + 2.2 * k); ring.material.opacity = ringT < 0.9 ? (1 - k) * 0.9 : 0;

      while (spawn > 0) {
        const f = feathers.find(f => !f.m.visible); if (!f) { spawn = 0; break; }
        spawn--;
        Object.assign(f, { t: 0, life: 3 + Math.random() * 2, x: (Math.random() - 0.5) * 1.2, z: (Math.random() - 0.5) * 0.6,
          y0: 0.7 + Math.random() * 0.6, spin: (Math.random() - 0.5) * 4, phase: Math.random() * 6 });
        f.m.visible = true;
      }
      for (const f of feathers) {
        if (!f.m.visible) continue;
        f.t += dt;
        const u = f.t / f.life;
        if (u >= 1) { f.m.visible = false; continue; }
        f.m.position.set(f.x + 0.12 * Math.sin(f.t * 2.2 + f.phase), f.y0 * (1 - u) + 0.02, f.z + 0.06 * Math.cos(f.t * 1.7 + f.phase));
        f.m.rotation.set(0.6 * Math.sin(f.t * 2.2 + f.phase), f.t * f.spin, 0.9 * Math.sin(f.t * 2.2 + f.phase + 1));
        f.m.material.opacity = Math.min(1, f.t * 3) * (1 - Math.max(0, (u - 0.7) / 0.3));
      }
    },
  };
  return api;
}
