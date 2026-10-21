// Image side of the scan: marker refinement, homography, perspective warp, white balance, line erase.
// C# port of web/vision.js with the same thresholds. This is the OpenCV swap point
// (Imgproc.getPerspectiveTransform / warpPerspective / morphologyEx + inpaint); the signatures stay.
//
// Image convention: Color32[] rows bottom-up (Unity Texture2D), coordinates in pixels, y up.
using UnityEngine;

namespace DoodLive
{
    public static class PageWarp
    {
        /// <summary>H (row-major 9) with H * src[i] ~ dst[i] for 4 point pairs, or null.</summary>
        public static double[] Homography(Vector2[] src, Vector2[] dst)
        {
            var A = new double[8, 9];
            for (int i = 0; i < 4; i++)
            {
                double x = src[i].x, y = src[i].y, u = dst[i].x, v = dst[i].y;
                double[] r0 = { x, y, 1, 0, 0, 0, -u * x, -u * y, u };
                double[] r1 = { 0, 0, 0, x, y, 1, -v * x, -v * y, v };
                for (int c = 0; c < 9; c++) { A[i * 2, c] = r0[c]; A[i * 2 + 1, c] = r1[c]; }
            }
            for (int c = 0; c < 8; c++)
            {
                int p = c;
                for (int r = c + 1; r < 8; r++) if (System.Math.Abs(A[r, c]) > System.Math.Abs(A[p, c])) p = r;
                if (System.Math.Abs(A[p, c]) < 1e-12) return null;
                for (int k = 0; k < 9; k++) { var t = A[c, k]; A[c, k] = A[p, k]; A[p, k] = t; }
                for (int r = 0; r < 8; r++)
                {
                    if (r == c) continue;
                    double f = A[r, c] / A[c, c];
                    for (int k = c; k < 9; k++) A[r, k] -= f * A[c, k];
                }
            }
            var h = new double[9];
            for (int i = 0; i < 8; i++) h[i] = A[i, 8] / A[i, i];
            h[8] = 1;
            return h;
        }

        public static Vector2 Apply(double[] H, double x, double y)
        {
            double w = H[6] * x + H[7] * y + H[8];
            return new Vector2((float)((H[0] * x + H[1] * y + H[2]) / w), (float)((H[3] * x + H[4] * y + H[5]) / w));
        }

        /// <summary>
        /// Centroid of the best solid dark square within radius of each expected point, or null if any is missing.
        /// Same blob rules as vision.js findBlob.
        /// </summary>
        public static Vector2[] RefineMarkers(Color32[] img, int W, int H, Vector2[] expected, float radius)
        {
            var outPts = new Vector2[4];
            for (int m = 0; m < 4; m++)
            {
                var c = FindBlob(img, W, H, expected[m], radius);
                if (c == null) return null;
                outPts[m] = c.Value;
            }
            return outPts;
        }

        static Vector2? FindBlob(Color32[] img, int W, int H, Vector2 e, float r)
        {
            int x0 = Mathf.Max(0, Mathf.RoundToInt(e.x - r)), y0 = Mathf.Max(0, Mathf.RoundToInt(e.y - r));
            int x1 = Mathf.Min(W, Mathf.RoundToInt(e.x + r)), y1 = Mathf.Min(H, Mathf.RoundToInt(e.y + r));
            int w = x1 - x0, h = y1 - y0;
            if (w < 8 || h < 8) return null;
            var lum = new float[w * h];
            double sum = 0;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    var p = img[(y0 + y) * W + x0 + x];
                    float l = 0.299f * p.r + 0.587f * p.g + 0.114f * p.b;
                    lum[y * w + x] = l; sum += l;
                }
            float thr = Mathf.Min(110f, (float)(sum / (w * h)) * 0.5f);
            var label = new int[w * h];
            var stack = new System.Collections.Generic.Stack<int>();
            float minA = w * h * 0.004f, maxA = w * h * 0.5f, bestScore = -1;
            Vector2 best = default;
            int id = 0;
            for (int s = 0; s < w * h; s++)
            {
                if (label[s] != 0 || lum[s] > thr) continue;
                label[s] = ++id; stack.Push(s);
                int a = 0, bx0 = w, by0 = h, bx1 = 0, by1 = 0; double sx = 0, sy = 0;
                while (stack.Count > 0)
                {
                    int p = stack.Pop(), px = p % w, py = p / w;
                    a++; sx += px; sy += py;
                    if (px < bx0) bx0 = px; if (px > bx1) bx1 = px; if (py < by0) by0 = py; if (py > by1) by1 = py;
                    if (px > 0) Visit(p - 1); if (px < w - 1) Visit(p + 1);
                    if (py > 0) Visit(p - w); if (py < h - 1) Visit(p + w);
                }
                if (a < minA || a > maxA) continue;
                if (bx0 == 0 || by0 == 0 || bx1 == w - 1 || by1 == h - 1) continue; // cut by the window
                int bw = bx1 - bx0 + 1, bh = by1 - by0 + 1;
                float fill = (float)a / (bw * bh), asp = (float)bw / bh;
                if (fill < 0.6f || asp < 0.5f || asp > 2f) continue;
                float score = a * fill;
                if (score > bestScore) { bestScore = score; best = new Vector2(x0 + (float)(sx / a), y0 + (float)(sy / a)); }
            }
            return bestScore < 0 ? (Vector2?)null : best;

            void Visit(int q)
            {
                if (label[q] != 0 || lum[q] > thr) return;
                label[q] = id; stack.Push(q);
            }
        }

        /// <summary>
        /// Warp the template's art rectangle into an N x N texture (rows bottom-up, so row N-1 = top of the art).
        /// H maps template px (y down from the top of the sheet) to image px (y up).
        /// </summary>
        public static Color32[] WarpArt(Color32[] src, int W, int Hh, double[] H, Rect art, int N = 1024)
        {
            var o = new Color32[N * N];
            var white = new Color32(255, 255, 255, 255);
            for (int j = 0; j < N; j++)
            {
                double ty = art.y + (1 - (j + 0.5) / N) * art.height; // texture row j counts up from the art's bottom
                for (int i = 0; i < N; i++)
                {
                    double tx = art.x + (i + 0.5) / N * art.width;
                    double w = H[6] * tx + H[7] * ty + H[8];
                    double x = (H[0] * tx + H[1] * ty + H[2]) / w - 0.5;
                    double y = (H[3] * tx + H[4] * ty + H[5]) / w - 0.5;
                    int xi = (int)System.Math.Floor(x), yi = (int)System.Math.Floor(y), k = j * N + i;
                    if (xi < 0 || yi < 0 || xi >= W - 1 || yi >= Hh - 1) { o[k] = white; continue; }
                    float fx = (float)(x - xi), fy = (float)(y - yi);
                    int p = yi * W + xi;
                    Color32 a = src[p], b = src[p + 1], c = src[p + W], d = src[p + W + 1];
                    o[k] = new Color32(
                        Bilerp(a.r, b.r, c.r, d.r, fx, fy), Bilerp(a.g, b.g, c.g, d.g, fx, fy),
                        Bilerp(a.b, b.b, c.b, d.b, fx, fy), 255);
                }
            }
            return o;
        }

        static byte Bilerp(byte a, byte b, byte c, byte d, float fx, float fy) =>
            (byte)Mathf.Clamp((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy, 0, 255);

        /// <summary>Paper-white balance (85th / 1st percentile per channel) + gentle saturation boost, in place.</summary>
        public static void WhiteBalance(Color32[] d, float sat = 1.25f)
        {
            int n = d.Length;
            var hr = new int[256]; var hg = new int[256]; var hb = new int[256];
            for (int i = 0; i < n; i++) { hr[d[i].r]++; hg[d[i].g]++; hb[d[i].b]++; }
            int[] white = { Hi(hr), Hi(hg), Hi(hb) }, black = { Lo(hr), Lo(hg), Lo(hb) };
            for (int i = 0; i < n; i++)
            {
                float r = (d[i].r - black[0]) / (float)(white[0] - black[0]);
                float g = (d[i].g - black[1]) / (float)(white[1] - black[1]);
                float b = (d[i].b - black[2]) / (float)(white[2] - black[2]);
                float l = 0.299f * r + 0.587f * g + 0.114f * b;
                r = l + (r - l) * sat; g = l + (g - l) * sat; b = l + (b - l) * sat;
                d[i] = new Color32(C255(r * 250), C255(g * 250), C255(b * 250), 255);
            }

            int Hi(int[] h) { int acc = 0; for (int v = 255; v >= 0; v--) { acc += h[v]; if (acc > n * 0.15f) return Mathf.Max(v, 60); } return 255; }
            int Lo(int[] h) { int acc = 0; for (int v = 0; v < 256; v++) { acc += h[v]; if (acc > n * 0.01f) return Mathf.Min(v, 80); } return 0; }
        }

        static byte C255(float v) => (byte)(v < 0 ? 0 : v > 255 ? 255 : v);

        /// <summary>Fill thin dark ink lines with the brightest nearby non-ink colour (returns a new array).</summary>
        public static Color32[] EraseLines(Color32[] src, int W, int H, int radius = 4)
        {
            var o = (Color32[])src.Clone();
            int[,] dirs = { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 }, { 1, 1 }, { -1, -1 }, { 1, -1 }, { -1, 1 } };
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++)
                {
                    int i = y * W + x;
                    if (!IsInk(src[i])) continue;
                    int best = -1, bi = i;
                    for (int r = 1; r <= radius; r++)
                        for (int k = 0; k < 8; k++)
                        {
                            int xx = x + dirs[k, 0] * r, yy = y + dirs[k, 1] * r;
                            if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
                            int j = yy * W + xx;
                            if (IsInk(src[j])) continue;
                            int s = src[j].r + src[j].g + src[j].b;
                            if (s > best) { best = s; bi = j; }
                        }
                    if (best >= 0) o[i] = src[bi];
                }
            return o;
        }

        static bool IsInk(Color32 c)
        {
            int mx = Mathf.Max(c.r, Mathf.Max(c.g, c.b)), mn = Mathf.Min(c.r, Mathf.Min(c.g, c.b));
            return mx < 175 && mx - mn < 45;
        }
    }
}
