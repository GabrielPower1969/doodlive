// Runs MarkerDetector + SheetIdentifier on tests/vision/make_synthetic.py frames and reports accuracy.
// Pass: >= 95 % of sheets found and identified with every marker within 2.5 % of the frame's short side, never the
// wrong story, and no sheet reported on frames without one. Debug one frame: dotnet run -c Release -- DIR 12.pgm [gt]
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using DoodLive.Vision;

class Program
{
    static int Main(string[] args)
    {
        string dir = args[0];
        if (args.Length > 2 && args[2] == "gt") { GtCheck(dir, args[1]); return 0; }
        if (args.Length > 1) { MarkerDetector.Trace = Console.WriteLine; Debug(dir, args[1]); return 0; }
        string root = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../"));
        var sigs = SheetIdentifier.Parse(File.ReadAllText(Path.Combine(root, "unity/Assets/DoodLive/Resources/sheet_signatures.json")));
        var truth = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "truth.json"))).RootElement;
        int pos = 0, found = 0, accurate = 0, story = 0, exact = 0, neg = 0, falsePos = 0, wrongStory = 0; double ms = 0, worstMs = 0;
        var fails = new List<string>();
        foreach (var e in truth.EnumerateArray())
        {
            var (lum, w, h) = ReadPgm(Path.Combine(dir, e.GetProperty("file").GetString()));
            // detection runs on a copy whose short side is ~360 px, as in the app; identification on the full frame
            var (small, sw, shh, k) = Downscale(lum, w, h, 360);
            var sw1 = Stopwatch.StartNew();
            var cands = MarkerDetector.DetectTop(small, sw, shh, 10);
            var r = cands.Count > 0 ? cands[0] : null;
            double t = sw1.Elapsed.TotalMilliseconds; ms += t; worstMs = Math.Max(worstMs, t);
            bool hasSheet = e.GetProperty("sheet").ValueKind != JsonValueKind.Null;
            if (!hasSheet)
            {   // a "found" here is harmless unless the title check also accepts it
                neg++;
                foreach (var c in cands)
                {
                    var full = new P2[4]; for (int i = 0; i < 4; i++) full[i] = new P2((c.Points[i].X + 0.5) * k - 0.5, (c.Points[i].Y + 0.5) * k - 0.5);
                    var mm = SheetIdentifier.Identify(lum, w, h, full, sigs);
                    if (mm != null) { falsePos++; fails.Add($"{e.GetProperty("file")} false positive {mm.Sheet.Name} ncc {mm.Ncc:0.00}"); break; }
                }
                continue;
            }
            pos++;
            string name = e.GetProperty("sheet").GetString();
            if (r == null) { fails.Add($"{e.GetProperty("file")} {name}: not found"); continue; }
            found++;
            SheetMatch m = null;
            foreach (var c in cands)
            {
                var full = new P2[4]; for (int i = 0; i < 4; i++) full[i] = new P2((c.Points[i].X + 0.5) * k - 0.5, (c.Points[i].Y + 0.5) * k - 0.5);
                full = MarkerDetector.Refine(lum, w, h, full, c.MarkerPx * k * 0.9);
                var mm = SheetIdentifier.Identify(lum, w, h, full, sigs);
                if (mm != null && (m == null || mm.Ncc > m.Ncc)) m = mm;
            }
            var gt = e.GetProperty("markers");
            if (m == null)
            {
                double bestN = -1; string bn = "";
                foreach (var c in cands)
                {
                    var full = new P2[4]; for (int i = 0; i < 4; i++) full[i] = new P2((c.Points[i].X + 0.5) * k - 0.5, (c.Points[i].Y + 0.5) * k - 0.5);
                    var mm = SheetIdentifier.Identify(lum, w, h, full, sigs, -1);
                    if (mm != null && mm.Ncc > bestN) { bestN = mm.Ncc; bn = mm.Sheet.Name; }
                }
                fails.Add($"{e.GetProperty("file")} {name}: markers found, sheet not identified (best {bn} {bestN:0.00}, {w}x{h})"); continue;
            }
            double tol = Math.Min(w, h) * 0.025, err = 0;
            for (int i = 0; i < 4; i++)
            {
                double gx = gt[i][0].GetDouble(), gy = gt[i][1].GetDouble();
                err = Math.Max(err, Math.Sqrt(Math.Pow(m.Points[i].X - gx, 2) + Math.Pow(m.Points[i].Y - gy, 2)));
            }
            // story of the true sheet = story of its signature (angel themes share "angel"); exact for every story pack
            string trueStory = sigs.Find(g => g.Name == name)?.Story ?? (name.StartsWith("david") ? "david-goliath" : "angel");
            bool sameStory = m.Sheet.Story == trueStory;
            if (err <= tol) accurate++; else fails.Add($"{e.GetProperty("file")} {name}: corner error {err:0.0}px (tol {tol:0.0}) as {m.Sheet.Name} ncc {m.Ncc:0.00}");
            if (sameStory) story++; else wrongStory++;
            if (!sameStory) fails.Add($"{e.GetProperty("file")} {name}: WRONG STORY {m.Sheet.Name} ncc {m.Ncc:0.00}");
            if (m.Sheet.Name.Split('-')[0] == name.Split('-')[0]) exact++;
        }
        foreach (var f in fails) Console.WriteLine("  " + f);
        Console.WriteLine($"sheets {pos}: found {found}, corners right {accurate}, story right {story}, theme right {exact}; " +
                          $"no-sheet frames {neg}: false positives {falsePos}; detect {ms / truth.GetArrayLength():0.0} ms avg, {worstMs:0} ms worst");
        // a missed frame only means "hold still a moment"; a wrong story or a false sheet would be a real bug
        bool pass = accurate >= pos * 0.95 && wrongStory == 0 && falsePos == 0;
        Console.WriteLine(pass ? "PASS" : "FAIL");
        return pass ? 0 : 1;
    }

    static void GtCheck(string dir, string file)
    {
        string root = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../"));
        var sigs = SheetIdentifier.Parse(File.ReadAllText(Path.Combine(root, "unity/Assets/DoodLive/Resources/sheet_signatures.json")));
        var truth = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "truth.json"))).RootElement;
        foreach (var e in truth.EnumerateArray())
        {
            if (e.GetProperty("file").GetString() != file) continue;
            var (lum, w, h) = ReadPgm(Path.Combine(dir, file));
            var gt = e.GetProperty("markers"); var p = new P2[4];
            for (int i = 0; i < 4; i++) p[i] = new P2(gt[i][0].GetDouble(), gt[i][1].GetDouble());
            var H = Homography.Solve(MarkerDetector.TemplateMarkers, p);
            foreach (var s in sigs)
            {
                var g = SheetIdentifier.Warp(lum, w, h, H, s.Region, s.W, s.H);
                Console.WriteLine($"{s.Name,-18} ncc at truth {SheetIdentifier.Ncc(g, s.Lum):0.00}");
            }
            // dump the warped title band for a look
            var g0 = SheetIdentifier.Warp(lum, w, h, H, sigs[0].Region, sigs[0].W * 4, sigs[0].H * 4);
            var sb = new System.Text.StringBuilder($"P2 {sigs[0].W * 4} {sigs[0].H * 4} 255\n");
            foreach (var v in g0) sb.Append((int)v).Append(' ');
            File.WriteAllText(Path.Combine(dir, file + ".title.pgm"), sb.ToString());
        }
    }

    static void Debug(string dir, string file)
    {
        var (lum, w, h) = ReadPgm(Path.Combine(dir, file));
        var (small, sw, shh, k) = Downscale(lum, w, h, 360);
        Console.WriteLine($"{file}: {w}x{h} -> {sw}x{shh}");
        var r = MarkerDetector.Detect(small, sw, shh, 0.0);
        Console.WriteLine(r == null ? "none" : $"best score {r.Score:0.00} pts {string.Join(" ", r.Points)}");
    }

    static (byte[], int, int) ReadPgm(string path)
    {
        var b = File.ReadAllBytes(path); int i = 0, f = 0; var v = new int[3];
        // "P5 W H 255\n"
        while (b[i] != (byte)' ') i++;
        for (; f < 3; f++)
        {
            while (b[i] == ' ' || b[i] == '\n') i++;
            int s = i; while (b[i] != ' ' && b[i] != '\n') i++;
            v[f] = int.Parse(System.Text.Encoding.ASCII.GetString(b, s, i - s));
        }
        i++;
        var lum = new byte[v[0] * v[1]]; Array.Copy(b, i, lum, 0, lum.Length);
        return (lum, v[0], v[1]);
    }

    static (byte[], int, int, double) Downscale(byte[] lum, int w, int h, int shortSide)
    {
        int f = Math.Max(1, (int)Math.Round((double)Math.Min(w, h) / shortSide));
        if (f == 1) return (lum, w, h, 1); int sw = w / f, sh = h / f; var o = new byte[sw * sh];
        for (int y = 0; y < sh; y++)
            for (int x = 0; x < sw; x++)
            {
                int acc = 0; for (int dy = 0; dy < f; dy++) for (int dx = 0; dx < f; dx++) acc += lum[(y * f + dy) * w + x * f + dx];
                o[y * sw + x] = (byte)(acc / (f * f));
            }
        return (o, sw, sh, f);
    }
}
