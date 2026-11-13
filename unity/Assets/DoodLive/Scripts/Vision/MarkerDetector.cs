// Finds a DoodLive sheet in a camera frame by its 4 printed corner markers (solid black squares), with no prior.
//
// Why not ARCore image tracking alone: a blank colouring page is mostly white with a few long outlines, so
// `arcoreimg eval-img` scores it 0-15 / 100 and ARCore never locks on; colouring then changes the inside, so the
// inside can never be the anchor. The markers are on every sheet, never coloured, and survive print, screen, blur and
// any colouring (docs/LESSONS.md L49). ARCore image tracking stays as a second path for coloured pages.
//
// Pure C# (no UnityEngine) so tests/vision can run it with `dotnet`. Image: 8-bit luminance, row-major, any row order
// (the returned points use the same pixel coordinates). Cost: ~5-15 ms on a 360 px wide frame.
using System;
using System.Collections.Generic;

namespace DoodLive.Vision
{
    public struct P2
    {
        public double X, Y;
        public P2(double x, double y) { X = x; Y = y; }
        public override string ToString() => $"({X:0.0},{Y:0.0})";
    }

    public sealed class MarkerResult
    {
        public P2[] Points;        // 4 marker centres in template order TL TR BR BL (orientation: best guess, see Rotations)
        public double Score;       // 0..1, higher is better
        public double[] H;         // template px -> image px for Points
        public double MarkerPx;    // mean marker side in image px
    }

    public static class MarkerDetector
    {
        // Sheet geometry (template px). All sheets share it (web/assets/template.json, design.json sheet).
        public static P2[] TemplateMarkers = { new P2(62, 225), new P2(1178, 225), new P2(1178, 1568), new P2(62, 1568) };
        public static double TemplateMarkerSize = 64;
        public static double[] TemplateArt = { 120, 283, 1000, 1227 };

        /// <summary>Optional trace for tests (tests/vision debug mode); null in the app.</summary>
        public static Action<string> Trace;

        struct Blob { public int Area; public double Cx, Cy, Mean; public int X0, Y0, X1, Y1; }

        /// <summary>Best 4-marker quad, or null. minScore: 0.5 is a good default.</summary>
        public static MarkerResult Detect(byte[] lum, int w, int h, double minScore = 0.5, bool yDown = true)
        {
            var all = DetectTop(lum, w, h, 1, minScore, yDown);
            return all.Count > 0 ? all[0] : null;
        }

        /// <summary>
        /// The k best distinct quads (best first). The title check (SheetIdentifier) picks among them, so a background
        /// square that stood in for one marker loses to the true quad there.
        /// </summary>
        public static List<MarkerResult> DetectTop(byte[] lum, int w, int h, int k, double minScore = 0.5, bool yDown = true)
        {
            var found = new List<MarkerResult>();
            var blobs = DarkBlobs(lum, w, h);
            if (Trace != null) foreach (var b in blobs) Trace($"blob {b.Cx:0.0},{b.Cy:0.0} area {b.Area} mean {b.Mean:0}");
            if (blobs.Count < 4) return found;
            blobs.Sort((a, b) => b.Area.CompareTo(a.Area));
            if (blobs.Count > 24) blobs.RemoveRange(24, blobs.Count - 24);
            int n = blobs.Count;
            var q = new P2[4]; var idx = new int[4];
            for (int a = 0; a < n; a++)
            for (int b = a + 1; b < n; b++)
            for (int c = b + 1; c < n; c++)
            for (int d = c + 1; d < n; d++)
            {
                int amax = blobs[a].Area, amin = blobs[d].Area;      // sorted by area
                if (amax > amin * 5) continue;
                idx[0] = a; idx[1] = b; idx[2] = c; idx[3] = d;
                if (!OrderConvex(blobs, idx, q)) continue;
                MarkerResult best = null;
                for (int rot = 0; rot < 8; rot++)       // 4 rotations x 2 directions (y-up images mirror the order)
                {
                    var pts = new P2[4]; var bl = new Blob[4];
                    for (int i = 0; i < 4; i++)
                    {
                        int j = rot < 4 ? (i + rot) % 4 : (rot - i + 4) % 4;
                        pts[i] = q[j]; bl[i] = blobs[idx[j]];
                    }
                    if (!FacesCamera(pts, yDown)) continue;
                    var H = Homography.Solve(TemplateMarkers, pts);
                    if (H == null) continue;
                    if (Trace != null) Trace($"quad {pts[0]} {pts[1]} {pts[2]} {pts[3]}");
                    double s = ScoreQuad(lum, w, h, H, bl, out double mpx);
                    if (Trace != null) Trace($"  score {s:0.000}");
                    if (s > (best?.Score ?? minScore)) best = new MarkerResult { Points = pts, Score = s, H = H, MarkerPx = mpx };
                }
                if (best == null) continue;
                found.Add(best);
            }
            found.Sort((x, y) => y.Score.CompareTo(x.Score));
            if (found.Count > k) found.RemoveRange(k, found.Count - k);
            return found;
        }

        /// <summary>
        /// Refine 4 rough marker centres (e.g. found on a downscaled copy) on the full-resolution frame: the solid dark
        /// blob nearest each rough point within `radius` px (same blob rules as web/vision.js findBlob). Points that find
        /// no blob keep their rough position.
        /// </summary>
        public static P2[] Refine(byte[] lum, int w, int h, P2[] rough, double radius)
        {
            var o = new P2[4];
            for (int m = 0; m < 4; m++) o[m] = FindBlobNear(lum, w, h, rough[m], radius) ?? rough[m];
            return o;
        }

        static P2? FindBlobNear(byte[] lum, int w, int h, P2 e, double r)
        {
            int x0 = Math.Max(0, (int)Math.Round(e.X - r)), y0 = Math.Max(0, (int)Math.Round(e.Y - r));
            int x1 = Math.Min(w, (int)Math.Round(e.X + r)), y1 = Math.Min(h, (int)Math.Round(e.Y + r));
            int ww = x1 - x0, hh = y1 - y0;
            if (ww < 6 || hh < 6) return null;
            double sum = 0;
            for (int y = y0; y < y1; y++) for (int x = x0; x < x1; x++) sum += lum[y * w + x];
            double thr = Math.Min(110, sum / (ww * hh) * 0.5);
            var label = new bool[ww * hh]; var stack = new int[ww * hh];
            P2? best = null; double bestD = double.MaxValue; int minA = Math.Max(6, (int)(r * r * 0.02));
            for (int s0 = 0; s0 < ww * hh; s0++)
            {
                int sx0 = s0 % ww, sy0 = s0 / ww;
                if (label[s0] || lum[(y0 + sy0) * w + x0 + sx0] > thr) continue;
                int sp = 0; stack[sp++] = s0; label[s0] = true;
                int a = 0; double cx = 0, cy = 0; int bx0 = ww, by0 = hh, bx1 = 0, by1 = 0;
                while (sp > 0)
                {
                    int p = stack[--sp], px = p % ww, py = p / ww;
                    a++; cx += px; cy += py;
                    if (px < bx0) bx0 = px; if (px > bx1) bx1 = px; if (py < by0) by0 = py; if (py > by1) by1 = py;
                    void Push(int q, int qx, int qy) { if (!label[q] && lum[(y0 + qy) * w + x0 + qx] <= thr) { label[q] = true; stack[sp++] = q; } }
                    if (px > 0) Push(p - 1, px - 1, py); if (px < ww - 1) Push(p + 1, px + 1, py);
                    if (py > 0) Push(p - ww, px, py - 1); if (py < hh - 1) Push(p + ww, px, py + 1);
                }
                if (a < minA || bx0 == 0 || by0 == 0 || bx1 == ww - 1 || by1 == hh - 1) continue;
                int bw = bx1 - bx0 + 1, bh = by1 - by0 + 1; double fill = (double)a / (bw * bh), asp = (double)bw / bh;
                if (fill < 0.5 || asp < 0.33 || asp > 3) continue;
                var c = new P2(x0 + cx / a, y0 + cy / a); double d = Dist(c, e);
                if (d < bestD) { bestD = d; best = c; }
            }
            return best;
        }

        // ---- blobs: local-adaptive dark threshold + 4-connected components ----
        static List<Blob> DarkBlobs(byte[] lum, int w, int h)
        {
            var ii = new long[(w + 1) * (h + 1)];
            for (int y = 0; y < h; y++)
            {
                long row = 0;
                for (int x = 0; x < w; x++) { row += lum[y * w + x]; ii[(y + 1) * (w + 1) + x + 1] = ii[y * (w + 1) + x + 1] + row; }
            }
            int r = Math.Max(6, Math.Min(w, h) / 10);
            var dark = new bool[w * h];
            for (int y = 0; y < h; y++)
            {
                int y0 = Math.Max(0, y - r), y1 = Math.Min(h, y + r + 1);
                for (int x = 0; x < w; x++)
                {
                    int x0 = Math.Max(0, x - r), x1 = Math.Min(w, x + r + 1);
                    long sum = ii[y1 * (w + 1) + x1] - ii[y0 * (w + 1) + x1] - ii[y1 * (w + 1) + x0] + ii[y0 * (w + 1) + x0];
                    double mean = (double)sum / ((x1 - x0) * (y1 - y0));
                    int l = lum[y * w + x];
                    dark[y * w + x] = l < mean * 0.62 && l < 125;
                }
            }
            var label = new int[w * h]; var stack = new int[w * h]; var outB = new List<Blob>();
            int minA = Math.Max(10, w * h / 40000), maxA = w * h / 40;
            for (int s = 0; s < w * h; s++)
            {
                if (!dark[s] || label[s] != 0) continue;
                int sp = 0; stack[sp++] = s; label[s] = 1;
                int area = 0; long sx = 0, sy = 0, sl = 0; int bx0 = w, by0 = h, bx1 = 0, by1 = 0; bool tooBig = false;
                while (sp > 0)
                {
                    int p = stack[--sp], px = p % w, py = p / w;
                    area++; sx += px; sy += py; sl += lum[p];
                    if (px < bx0) bx0 = px; if (px > bx1) bx1 = px; if (py < by0) by0 = py; if (py > by1) by1 = py;
                    if (area > maxA) tooBig = true;
                    if (px > 0 && dark[p - 1] && label[p - 1] == 0) { label[p - 1] = 1; stack[sp++] = p - 1; }
                    if (px < w - 1 && dark[p + 1] && label[p + 1] == 0) { label[p + 1] = 1; stack[sp++] = p + 1; }
                    if (py > 0 && dark[p - w] && label[p - w] == 0) { label[p - w] = 1; stack[sp++] = p - w; }
                    if (py < h - 1 && dark[p + w] && label[p + w] == 0) { label[p + w] = 1; stack[sp++] = p + w; }
                }
                if (tooBig || area < minA) continue;
                if (bx0 == 0 || by0 == 0 || bx1 == w - 1 || by1 == h - 1) continue;
                int bw = bx1 - bx0 + 1, bh = by1 - by0 + 1;
                double fill = (double)area / (bw * bh), asp = (double)bw / bh;
                if (fill < 0.5 || asp < 0.33 || asp > 3) continue;
                outB.Add(new Blob { Area = area, Cx = (double)sx / area, Cy = (double)sy / area, Mean = (double)sl / area, X0 = bx0, Y0 = by0, X1 = bx1, Y1 = by1 });
            }
            return outB;
        }

        // Order 4 blob centres around their centroid; false if not a proper convex quad.
        static bool OrderConvex(List<Blob> blobs, int[] idx, P2[] q)
        {
            double mx = 0, my = 0;
            for (int i = 0; i < 4; i++) { mx += blobs[idx[i]].Cx; my += blobs[idx[i]].Cy; }
            mx /= 4; my /= 4;
            var ang = new double[4];
            for (int i = 0; i < 4; i++) ang[i] = Math.Atan2(blobs[idx[i]].Cy - my, blobs[idx[i]].Cx - mx);
            Array.Sort(ang, idx);
            for (int i = 0; i < 4; i++) q[i] = new P2(blobs[idx[i]].Cx, blobs[idx[i]].Cy);
            int sign = 0;
            for (int i = 0; i < 4; i++)
            {
                P2 a = q[i], b = q[(i + 1) % 4], c = q[(i + 2) % 4];
                double cr = (b.X - a.X) * (c.Y - b.Y) - (b.Y - a.Y) * (c.X - b.X);
                int sg = Math.Sign(cr);
                if (sg == 0) return false;
                if (sign != 0 && sg != sign) return false;
                sign = sg;
            }
            // min side vs max side: a sheet seen at <= ~70 deg never gets thinner than 1:6
            double mn = double.MaxValue, mxs = 0;
            for (int i = 0; i < 4; i++) { double L = Dist(q[i], q[(i + 1) % 4]); mn = Math.Min(mn, L); mxs = Math.Max(mxs, L); }
            return mn * 6 > mxs && mn > 8;
        }

        /// <summary>
        /// True when TL TR BR BL run the same way round as on the printed page: a mirrored order would mean the page is
        /// seen from behind, which never happens. yDown: image row 0 is the top (camera images); false for Unity
        /// Color32 buffers (row 0 = bottom).
        /// </summary>
        public static bool FacesCamera(P2[] p, bool yDown)
        {
            double a = 0;
            for (int i = 0; i < 4; i++) { var u = p[i]; var v = p[(i + 1) % 4]; a += u.X * v.Y - v.X * u.Y; }
            return yDown ? a > 0 : a < 0;            // template TL TR BR BL is clockwise on screen = positive in y-down
        }

        static double Dist(P2 a, P2 b) => Math.Sqrt((a.X - b.X) * (a.X - b.X) + (a.Y - b.Y) * (a.Y - b.Y));

        // How much does this quad look like our sheet under H?
        //  - each blob's area matches the projected 64 px marker square
        //  - the paper ring right inside each marker and the art rectangle's border are light
        //  - the page is not seen from behind (orientation consistent)
        static double ScoreQuad(byte[] lum, int w, int h, double[] H, Blob[] bl, out double markerPx)
        {
            markerPx = 0; double sizeScore = 0; double ms = TemplateMarkerSize / 2;
            for (int i = 0; i < 4; i++)
            {
                var c = TemplateMarkers[i];
                var p0 = Homography.Apply(H, c.X - ms, c.Y - ms); var p1 = Homography.Apply(H, c.X + ms, c.Y - ms);
                var p2 = Homography.Apply(H, c.X + ms, c.Y + ms); var p3 = Homography.Apply(H, c.X - ms, c.Y + ms);
                double area = Math.Abs(Shoelace(p0, p1, p2, p3));
                if (area < 4) return 0;
                double ratio = bl[i].Area / area;
                if (ratio < 0.35 || ratio > 2.6) { Trace?.Invoke($"  size ratio {ratio:0.00} at marker {i}"); return 0; }
                sizeScore += 1 - Math.Min(1, Math.Abs(Math.Log(ratio)) / Math.Log(2.6));
                markerPx += Math.Sqrt(area);
            }
            sizeScore /= 4; markerPx /= 4;
            double darkRef = 0; for (int i = 0; i < 4; i++) darkRef += bl[i].Mean; darkRef /= 4;
            // paper ring: 8 points around each marker at 1.25 x its half size (white paper on every sheet)
            int light = 0, total = 0;
            for (int i = 0; i < 4; i++)
            {
                var c = TemplateMarkers[i];
                for (int k = 0; k < 8; k++)
                {
                    double a = k * Math.PI / 4, rr = ms * 1.9;
                    var p = Homography.Apply(H, c.X + rr * Math.Cos(a), c.Y + rr * Math.Sin(a));
                    int v = Sample(lum, w, h, p); if (v < 0) continue;       // off-frame (marker near the edge)
                    total++; if (v > darkRef + 40) light++;
                }
            }
            if (total < 16) { Trace?.Invoke("  ring off-frame"); return 0; }
            double ring = (double)light / total;
            if (ring < 0.6) { Trace?.Invoke($"  ring {ring:0.00}"); return 0; }
            // art rectangle: a 7 x 9 grid; colouring can be dark, but most of a page is not as dark as a marker
            int lit = 0, cnt = 0; double ax = TemplateArt[0], ay = TemplateArt[1], aw = TemplateArt[2], ah = TemplateArt[3];
            for (int gy = 0; gy < 9; gy++)
            for (int gx = 0; gx < 7; gx++)
            {
                var p = Homography.Apply(H, ax + aw * (gx + 0.5) / 7, ay + ah * (gy + 0.5) / 9);
                int v = Sample(lum, w, h, p); if (v < 0) continue;
                cnt++; if (v > darkRef + 30) lit++;
            }
            double art = cnt > 30 ? (double)lit / cnt : 0;
            if (art < 0.45) { Trace?.Invoke($"  art {art:0.00}"); return 0; }
            // side margins between the markers: white paper on almost every sheet (not wrath-p2), so a soft score only
            int ml = 0, mc = 0;
            foreach (var mx in new[] { TemplateMarkers[0].X, TemplateMarkers[1].X })
                for (double my = 330; my < 1470; my += 95)
                {
                    int v = Sample(lum, w, h, Homography.Apply(H, mx, my)); if (v < 0) continue;
                    mc++; if (v > darkRef + 45) ml++;
                }
            double margin = mc > 0 ? (double)ml / mc : 0;
            return 0.35 * sizeScore + 0.3 * ring + 0.2 * art + 0.15 * margin;
        }

        static double Shoelace(P2 a, P2 b, P2 c, P2 d) =>
            0.5 * ((a.X * b.Y - b.X * a.Y) + (b.X * c.Y - c.X * b.Y) + (c.X * d.Y - d.X * c.Y) + (d.X * a.Y - a.X * d.Y));

        public static int Sample(byte[] lum, int w, int h, P2 p)
        {
            int x = (int)Math.Round(p.X), y = (int)Math.Round(p.Y);
            if (x < 0 || y < 0 || x >= w || y >= h) return -1;
            return lum[y * w + x];
        }
    }

    public static class Homography
    {
        /// <summary>H (row-major 9) with H * src[i] ~ dst[i], or null.</summary>
        public static double[] Solve(P2[] src, P2[] dst)
        {
            var A = new double[8, 9];
            for (int i = 0; i < 4; i++)
            {
                double x = src[i].X, y = src[i].Y, u = dst[i].X, v = dst[i].Y;
                double[] r0 = { x, y, 1, 0, 0, 0, -u * x, -u * y, u };
                double[] r1 = { 0, 0, 0, x, y, 1, -v * x, -v * y, v };
                for (int c = 0; c < 9; c++) { A[i * 2, c] = r0[c]; A[i * 2 + 1, c] = r1[c]; }
            }
            for (int c = 0; c < 8; c++)
            {
                int p = c;
                for (int r = c + 1; r < 8; r++) if (Math.Abs(A[r, c]) > Math.Abs(A[p, c])) p = r;
                if (Math.Abs(A[p, c]) < 1e-12) return null;
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

        public static P2 Apply(double[] H, double x, double y)
        {
            double w = H[6] * x + H[7] * y + H[8];
            return new P2((H[0] * x + H[1] * y + H[2]) / w, (H[3] * x + H[4] * y + H[5]) / w);
        }
    }
}
