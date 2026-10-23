// Loads the Blender-built angel (pipeline/angel_build.py -> assets/model/angel.glb) and adapts it to the same
// object shape buildAngel() returns, so animate() and app.js work unchanged. Falls back to buildAngel() on error.
import * as THREE from 'three';
import { GLTFLoader } from './vendor/jsm/loaders/GLTFLoader.js';
import { makeMaterial, radialTexture, BONE_NAMES } from './angel.js';

const PAGE_PARTS = {   // glTF material name -> page-coloured material (same defaults as buildAngel)
  robe: [0xf4f4f8, { rim: 0.35 }],
  skin: [0xf3cdb4, { baseAmt: 0.95, roughness: 0.6, rim: 0.15 }],
  hair: [0x8a5a32, { roughness: 0.9, rim: 0.2, ink: 1 }],
  wing: [0xf7f5ef, { side: THREE.DoubleSide, rim: 0.4 }],
  gold: [0xd9a43a, { metalness: 0.85, roughness: 0.3, rim: 0.3 }],
  sash: [0xd9a43a, { metalness: 0.4, roughness: 0.5, rim: 0.2 }],
  cloud: [0xffffff, { baseAmt: 1, roughness: 1, rim: 0.3 }],
};

export async function loadAngelGLB(texture, url = 'assets/model/angel.glb') {
  const gltf = await new GLTFLoader().loadAsync(url);
  const model = gltf.scene;
  const root = new THREE.Group(); root.name = 'angel';
  const rig = new THREE.Group(); root.add(rig); rig.add(model);

  const B = {}, face = { lids: [], eyes: [], jaw: null, mouthIn: new THREE.Object3D() };
  let halo = null, cloud = null;
  const pageMats = {};
  model.traverse(o => {
    if (BONE_NAMES.includes(o.name)) B[o.name] = o;
    if (o.name === 'halo') halo = o;
    if (o.name === 'cloud') cloud = o;
    if (o.name === 'LidL' || o.name === 'LidR') face.lids.push(o);
    if (o.name === 'EyeL' || o.name === 'EyeR') face.eyes.push(o);
    if (o.name === 'LowerLip') face.jaw = o;
    if (o.isMesh) {
      o.castShadow = true; o.frustumCulled = false;
      // glTF UVs have v pointing down; our page texture is a CanvasTexture (flipY), so flip v back to "up"
      const uv = o.geometry.attributes.uv;
      if (uv && !o.geometry.userData.vFlipped) { for (let i = 0; i < uv.count; i++) uv.setY(i, 1 - uv.getY(i)); uv.needsUpdate = true; o.geometry.userData.vFlipped = true; }
      const n = (o.material?.name || '').replace(/\.\d+$/, '');
      if (PAGE_PARTS[n]) {
        o.material = pageMats[n] ||= makeMaterial(texture, PAGE_PARTS[n][0], PAGE_PARTS[n][1]);
      } else if (n === 'halo') {
        o.material = new THREE.MeshBasicMaterial({ color: 0xffe9a0, transparent: true, opacity: 0.95 });
      }  // eyes, lids, lashes, brows, lips keep the colours baked in the GLB
    }
  });
  for (const n of BONE_NAMES) if (!B[n]) console.warn('angel.glb: missing node', n);
  if (!halo) { halo = new THREE.Object3D(); B.head?.add(halo); }
  if (!cloud) { cloud = new THREE.Object3D(); root.add(cloud); }
  if (!face.jaw) face.jaw = new THREE.Object3D();
  // lids in the GLB hinge at the eye centre around local X; animate() lerps lid.rotation.x between open and shut
  for (const lid of face.lids) { lid.userData.restX = lid.rotation.x; }

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: radialTexture('rgba(255,240,190,0.85)'), depthWrite: false, transparent: true, blending: THREE.AdditiveBlending }));
  glow.scale.set(0.55, 0.55, 1); glow.position.set(0, 0.08, -0.15); (B.head || rig).add(glow);

  return { root, rig, bones: B, meshes: [], materials: pageMats, halo, glow, cloud, wings: [], face, talking: false, fromGLB: true };
}
