// Image side of DoodLive: marker detection, homography, perspective warp, colour cleanup, pose.
// Pure JS, no OpenCV — swap these functions for OpenCV(.js / for Unity) later without touching app.js.

/** Solve H (3x3, row-major array of 9) with H * src[i] ~ dst[i] for 4 point pairs. */
export function homography(src, dst) {
  const A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, v] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const h = solve(A, b);
  return h ? [...h, 1] : null;
}

function solve(A, b) {
  const n = b.length, M = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    if (Math.abs(M[p][c]) < 1e-12) return null;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((r, i) => r[n] / r[i]);
}

export const applyH = (H, x, y) => {
  const w = H[6] * x + H[7] * y + H[8];
  return [(H[0] * x + H[1] * y + H[2]) / w, (H[3] * x + H[4] * y + H[5]) / w];
};

/**
 * Find a solid dark square near each of 4 expected points.
 * img: ImageData; expected: [[x,y]x4] in img pixels; radius: search half-size in px.
 * Returns 4 centroids or null.
 */
export function detectMarkers(img, expected, radius) {
  const out = [];
  for (const [ex, ey] of expected) {
    const c = findBlob(img, ex, ey, radius);
    if (!c) return null;
    out.push(c);
  }
  // sanity: convex, ordered TL TR BR BL, not degenerate
  let sign = 0;
  for (let i = 0; i < 4; i++) {
    const a = out[i], b = out[(i + 1) % 4], c = out[(i + 2) % 4];
    const cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
    if (Math.abs(cr) < 1) return null;
    if (sign && Math.sign(cr) !== sign) return null;
    sign = Math.sign(cr);
  }
  return out;
}

function findBlob(img, ex, ey, r) {
  const { width: W, height: H, data } = img;
  const x0 = Math.max(0, Math.round(ex - r)), y0 = Math.max(0, Math.round(ey - r));
  const x1 = Math.min(W, Math.round(ex + r)), y1 = Math.min(H, Math.round(ey + r));
  const w = x1 - x0, h = y1 - y0;
  if (w < 8 || h < 8) return null;
  const lum = new Float32Array(w * h);
  let sum = 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = ((y0 + y) * W + x0 + x) * 4;
    const l = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    lum[y * w + x] = l; sum += l;
  }
  const thr = Math.min(110, (sum / (w * h)) * 0.5);
  const label = new Int32Array(w * h);
  const stack = [];
  let best = null, id = 0;
  const minA = (w * h) * 0.004, maxA = (w * h) * 0.5;
  for (let s = 0; s < w * h; s++) {
    if (label[s] || lum[s] > thr) continue;
    id++; label[s] = id; stack.push(s);
    let a = 0, sx = 0, sy = 0, bx0 = w, by0 = h, bx1 = 0, by1 = 0;
    while (stack.length) {
      const p = stack.pop(), px = p % w, py = (p / w) | 0;
      a++; sx += px; sy += py;
      if (px < bx0) bx0 = px; if (px > bx1) bx1 = px; if (py < by0) by0 = py; if (py > by1) by1 = py;
      for (const q of [p - 1, p + 1, p - w, p + w]) {
        if (q < 0 || q >= w * h || label[q] || lum[q] > thr) continue;
        if ((q === p - 1 && px === 0) || (q === p + 1 && px === w - 1)) continue;
        label[q] = id; stack.push(q);
      }
    }
    const bw = bx1 - bx0 + 1, bh = by1 - by0 + 1;
    if (a < minA || a > maxA) continue;
    if (bx0 === 0 || by0 === 0 || bx1 === w - 1 || by1 === h - 1) continue; // cut by window
    const fill = a / (bw * bh), asp = bw / bh;
    if (fill < 0.6 || asp < 0.5 || asp > 2) continue;
    const score = a * fill;
    if (!best || score > best.score) best = { score, x: x0 + sx / a, y: y0 + sy / a };
  }
  return best && [best.x, best.y];
}

/**
 * Warp the art rectangle of the template into an N x N texture.
 * src: ImageData of the camera frame; H: template px -> src px.
 */
export function warpArt(src, H, tpl, N = 1024) {
  const [ax, ay, aw, ah] = tpl.art;
  const out = new ImageData(N, N);
  const { width: W, height: Hh, data: s } = src, o = out.data;
  for (let j = 0; j < N; j++) {
    const ty = ay + ((j + 0.5) / N) * ah;
    for (let i = 0; i < N; i++) {
      const tx = ax + ((i + 0.5) / N) * aw;
      const w = H[6] * tx + H[7] * ty + H[8];
      const x = (H[0] * tx + H[1] * ty + H[2]) / w - 0.5;
      const y = (H[3] * tx + H[4] * ty + H[5]) / w - 0.5;
      const k = (j * N + i) * 4;
      const xi = Math.floor(x), yi = Math.floor(y);
      if (xi < 0 || yi < 0 || xi >= W - 1 || yi >= Hh - 1) { o[k] = o[k + 1] = o[k + 2] = 255; o[k + 3] = 255; continue; }
      const fx = x - xi, fy = y - yi, p = (yi * W + xi) * 4;
      for (let c = 0; c < 3; c++) {
        const a = s[p + c], b = s[p + 4 + c], cc = s[p + W * 4 + c], d = s[p + W * 4 + 4 + c];
        o[k + c] = (a * (1 - fx) + b * fx) * (1 - fy) + (cc * (1 - fx) + d * fx) * fy;
      }
      o[k + 3] = 255;
    }
  }
  return out;
}

/** Paper-white balance + gentle saturation boost, in place. */
export function whiteBalance(img, sat = 1.25) {
  const d = img.data, n = d.length / 4;
  const hist = [new Uint32Array(256), new Uint32Array(256), new Uint32Array(256)];
  for (let i = 0; i < d.length; i += 4) { hist[0][d[i]]++; hist[1][d[i + 1]]++; hist[2][d[i + 2]]++; }
  // paper is the majority bright colour: use the 85th percentile per channel as "white"
  const white = hist.map(h => { let acc = 0; for (let v = 255; v >= 0; v--) { acc += h[v]; if (acc > n * 0.15) return Math.max(v, 60); } return 255; });
  const black = hist.map(h => { let acc = 0; for (let v = 0; v < 256; v++) { acc += h[v]; if (acc > n * 0.01) return Math.min(v, 80); } return 0; });
  for (let i = 0; i < d.length; i += 4) {
    let r = (d[i] - black[0]) / (white[0] - black[0]);
    let g = (d[i + 1] - black[1]) / (white[1] - black[1]);
    let b = (d[i + 2] - black[2]) / (white[2] - black[2]);
    const l = 0.299 * r + 0.587 * g + 0.114 * b;
    r = l + (r - l) * sat; g = l + (g - l) * sat; b = l + (b - l) * sat;
    d[i] = clamp255(r * 250); d[i + 1] = clamp255(g * 250); d[i + 2] = clamp255(b * 250);
  }
  return img;
}
const clamp255 = v => (v < 0 ? 0 : v > 255 ? 255 : v);

/** Fill thin dark ink lines with the surrounding colour (returns a new ImageData). */
export function eraseLines(img, radius = 4) {
  const { width: W, height: H } = img;
  const src = img.data, out = new ImageData(new Uint8ClampedArray(src), W, H), o = out.data;
  const isInk = i => { const r = src[i], g = src[i + 1], b = src[i + 2]; const mx = Math.max(r, g, b); return mx < 175 && mx - Math.min(r, g, b) < 45; };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4;
    if (!isInk(i)) continue;
    // brightest non-ink neighbour in a small cross: keeps fills, drops the line
    let best = -1, bi = i;
    for (let r = 1; r <= radius; r++) for (const [dx, dy] of [[r, 0], [-r, 0], [0, r], [0, -r], [r, r], [-r, -r], [r, -r], [-r, r]]) {
      const xx = x + dx, yy = y + dy;
      if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
      const j = (yy * W + xx) * 4;
      if (isInk(j)) continue;
      const s = src[j] + src[j + 1] + src[j + 2];
      if (s > best) { best = s; bi = j; }
    }
    if (best >= 0) { o[i] = src[bi]; o[i + 1] = src[bi + 1]; o[i + 2] = src[bi + 2]; }
  }
  return out;
}

/**
 * Planar pose from a homography (template px -> screen px) and pinhole intrinsics.
 * Returns column-major 4x4 (OpenCV camera frame: x right, y down, z forward), units = template px.
 */
export function poseFromH(H, f, cx, cy) {
  // M = K^-1 H
  const m = [
    (H[0] - cx * H[6]) / f, (H[1] - cx * H[7]) / f, (H[2] - cx * H[8]) / f,
    (H[3] - cy * H[6]) / f, (H[4] - cy * H[7]) / f, (H[5] - cy * H[8]) / f,
    H[6], H[7], H[8],
  ];
  let c1 = [m[0], m[3], m[6]], c2 = [m[1], m[4], m[7]], t = [m[2], m[5], m[8]];
  const s = 2 / (len(c1) + len(c2));
  if (t[2] * s < 0) { c1 = c1.map(v => -v); c2 = c2.map(v => -v); t = t.map(v => -v); }
  let r1 = norm(c1), r2 = c2.map(v => v * s);
  // Gram-Schmidt
  const d = dot(r1, r2); r2 = norm(r2.map((v, i) => v - d * r1[i]));
  const r3 = cross(r1, r2);
  const T = t.map(v => v * s);
  return [r1[0], r1[1], r1[2], 0, r2[0], r2[1], r2[2], 0, r3[0], r3[1], r3[2], 0, T[0], T[1], T[2], 1];
}
const len = v => Math.hypot(v[0], v[1], v[2]);
const norm = v => { const l = len(v); return v.map(x => x / l); };
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
