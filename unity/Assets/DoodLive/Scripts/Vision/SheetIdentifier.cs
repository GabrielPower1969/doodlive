// Which sheet is it, and which way up? Compares the title band (田字格 characters + English title, never coloured)
// of the frame, warped through each of the 4 marker orderings, with the title band of every known sheet.
//
// Signatures come from tools/make_sheet_signatures.py (Resources/sheet_signatures.json): the printed sheet's title band
// [x, y, w, h] in template px, downsampled to a small luminance grid. Pure C# like MarkerDetector (tests/vision).
using System;
using System.Collections.Generic;

namespace DoodLive.Vision
{
    public sealed class SheetSignature
    {
        public string Name;          // reference name, e.g. "david-goliath-A4", "fiery-p1"
        public string Story;         // story id the sheet opens ("angel", "david-goliath", ...)
        public double[] Region;      // title band in template px: x, y, w, h
        public int W, H;             // grid size
        public byte[] Lum;           // W*H, row 0 = top
    }

    public sealed class SheetMatch
    {
        public SheetSignature Sheet;
        public P2[] Points;          // marker centres TL TR BR BL for this sheet's orientation
        public double[] H;           // template px -> image px
        public double Ncc;           // best normalised cross-correlation
        public double Margin;        // best - best of any other story
        public double OrientMargin;  // best - best of any other way up
        public int Rotation;         // which of the 8 orderings of the input points
    }

    public static class SheetIdentifier
    {
        /// <summary>
        /// Try the 8 orderings of the 4 marker points (rotations, both directions); for each, warp the title band and
        /// correlate with every signature. Returns the best match with NCC >= minNcc, or null.
        /// True matches score ~0.9; the most alike different stories ~0.45; a quad with one wrong corner stays below 0.6.
        /// </summary>
        public static SheetMatch Identify(byte[] lum, int w, int h, P2[] pts, IList<SheetSignature> sheets, double minNcc = 0.6, bool yDown = true)
        {
            // best per orientation, and per story, so a weak match must clearly beat the other ways up and the other stories
            SheetMatch best = null; var orientBest = new double[8]; var storyBest = new Dictionary<string, double>();
            for (int rot = 0; rot < 8; rot++)
            {
                orientBest[rot] = -1;
                var p = new P2[4];
                for (int i = 0; i < 4; i++) p[i] = pts[rot < 4 ? (i + rot) % 4 : (rot - i + 4) % 4];
                if (!MarkerDetector.FacesCamera(p, yDown)) continue;      // a mirror image = the page seen from behind
                var H = Homography.Solve(MarkerDetector.TemplateMarkers, p);
                if (H == null) continue;
                foreach (var s in sheets)
                {
                    var g = Warp(lum, w, h, H, s.Region, s.W, s.H);
                    if (g == null) continue;
                    double ncc = Ncc(g, s.Lum);
                    orientBest[rot] = Math.Max(orientBest[rot], ncc);
                    storyBest[s.Story] = Math.Max(storyBest.TryGetValue(s.Story, out var v) ? v : -1, ncc);
                    if (best == null || ncc > best.Ncc) best = new SheetMatch { Sheet = s, Points = p, H = H, Ncc = ncc, Rotation = rot };
                }
            }
            if (best == null) return null;
            double otherOrient = -1, otherStory = -1;
            for (int r = 0; r < 8; r++) if (r != best.Rotation) otherOrient = Math.Max(otherOrient, orientBest[r]);
            foreach (var kv in storyBest) if (kv.Key != best.Sheet.Story) otherStory = Math.Max(otherStory, kv.Value);
            best.Margin = best.Ncc - Math.Max(0, otherStory);
            best.OrientMargin = best.Ncc - Math.Max(0, otherOrient);
            bool strong = best.Ncc >= minNcc;
            bool clear = best.Ncc >= minNcc - 0.1 && best.OrientMargin >= 0.15 && best.Margin >= 0.1;   // 0.5: random quads on clutter reach ~0.45
            return strong || clear ? best : null;
        }

        /// <summary>Box-filtered warp of a template region into a gw x gh grid (row 0 = top), or null if off-image.</summary>
        public static double[] Warp(byte[] lum, int w, int h, double[] H, double[] region, int gw, int gh)
        {
            var g = new double[gw * gh]; const int ss = 3; int outside = 0;
            for (int j = 0; j < gh; j++)
            for (int i = 0; i < gw; i++)
            {
                double acc = 0; int n = 0;
                for (int sy = 0; sy < ss; sy++)
                for (int sx = 0; sx < ss; sx++)
                {
                    double tx = region[0] + region[2] * (i + (sx + 0.5) / ss) / gw;
                    double ty = region[1] + region[3] * (j + (sy + 0.5) / ss) / gh;
                    var p = Homography.Apply(H, tx, ty);
                    int v = Bilinear(lum, w, h, p.X, p.Y);
                    if (v < 0) { outside++; continue; }
                    acc += v; n++;
                }
                g[j * gw + i] = n > 0 ? acc / n : 255;
            }
            return outside > gw * gh * ss * ss / 4 ? null : g;
        }

        static int Bilinear(byte[] lum, int w, int h, double x, double y)
        {
            int xi = (int)Math.Floor(x), yi = (int)Math.Floor(y);
            if (xi < 0 || yi < 0 || xi >= w - 1 || yi >= h - 1) return -1;
            double fx = x - xi, fy = y - yi; int p = yi * w + xi;
            return (int)((lum[p] * (1 - fx) + lum[p + 1] * fx) * (1 - fy) + (lum[p + w] * (1 - fx) + lum[p + w + 1] * fx) * fy);
        }

        public static double Ncc(double[] a, byte[] b)
        {
            int n = a.Length; double ma = 0, mb = 0;
            for (int i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
            ma /= n; mb /= n;
            double sab = 0, saa = 0, sbb = 0;
            for (int i = 0; i < n; i++) { double da = a[i] - ma, db = b[i] - mb; sab += da * db; saa += da * da; sbb += db * db; }
            return saa < 1e-6 || sbb < 1e-6 ? 0 : sab / Math.Sqrt(saa * sbb);
        }

        /// <summary>Parse Resources/sheet_signatures.json (format written by tools/make_sheet_signatures.py).</summary>
        public static List<SheetSignature> Parse(string json)
        {
            // Tiny dedicated parser: [{"name":..,"story":..,"region":[..],"w":..,"h":..,"lum":"<base64>"}, ...]
            var list = new List<SheetSignature>();
            int i = 0;
            while ((i = json.IndexOf("\"name\"", i, StringComparison.Ordinal)) >= 0)
            {
                var s = new SheetSignature
                {
                    Name = Str(json, "name", i), Story = Str(json, "story", i),
                    W = (int)Num(json, "w", i), H = (int)Num(json, "h", i),
                    Lum = Convert.FromBase64String(Str(json, "lum", i)), Region = Arr(json, "region", i)
                };
                list.Add(s);
                i = json.IndexOf("\"lum\"", i, StringComparison.Ordinal) + 5;
            }
            return list;
        }

        static int Key(string s, string k, int from) => s.IndexOf("\"" + k + "\"", from, StringComparison.Ordinal) + k.Length + 2;
        static string Str(string s, string k, int from)
        {
            int a = s.IndexOf('"', s.IndexOf(':', Key(s, k, from)) + 1) + 1; return s.Substring(a, s.IndexOf('"', a) - a);
        }
        static double Num(string s, string k, int from)
        {
            int a = s.IndexOf(':', Key(s, k, from)) + 1, b = a;
            while (b < s.Length && (char.IsDigit(s[b]) || s[b] == '.' || s[b] == '-' || s[b] == ' ')) b++;
            return double.Parse(s.Substring(a, b - a), System.Globalization.CultureInfo.InvariantCulture);
        }
        static double[] Arr(string s, string k, int from)
        {
            int a = s.IndexOf('[', Key(s, k, from)) + 1, b = s.IndexOf(']', a);
            var parts = s.Substring(a, b - a).Split(',');
            var r = new double[parts.Length];
            for (int j = 0; j < parts.Length; j++) r[j] = double.Parse(parts[j], System.Globalization.CultureInfo.InvariantCulture);
            return r;
        }
    }
}
