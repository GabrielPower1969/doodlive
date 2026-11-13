// Runs StoryRetime.InferAnchors + StoryRetime.Core (unity/Assets/DoodLive/Story/StoryRetime.cs) under .NET, outside
// Unity, for tools/voice/test_retime.py. stdin: {"lines":[{id,t,maxSec,dur,anchor}], "items":[{t,anchor}],
// "durationAnchor":{}, "duration":s, "durs":{id:s}}; stdout: {"lines":[{t,maxSec}], "items":[t], "duration":s}.
// `dotnet harness.dll lufs <file.wav>`: VoiceDsp.Loudness of a 16-bit mono WAV (compare with ffmpeg ebur128).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.Json;
using DoodLive.Story;

static class Harness
{
    static StoryAnchor A(JsonElement e, string name)
    {
        if (!e.TryGetProperty(name, out var a) || a.ValueKind != JsonValueKind.Object) return null;
        return new StoryAnchor
        {
            line = a.TryGetProperty("line", out var l) ? l.GetString() : "",
            edge = a.TryGetProperty("edge", out var g) ? g.GetString() : "",
            dt = a.TryGetProperty("dt", out var d) ? d.GetSingle() : 0,
        };
    }
    static float F(JsonElement e, string n) => e.TryGetProperty(n, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetSingle() : 0;

    static void Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "lufs")   // VoiceDsp check: 16-bit mono PCM WAV -> integrated LUFS
        {
            var b = System.IO.File.ReadAllBytes(args[1]);
            int rate = BitConverter.ToInt32(b, 24), p = 12;
            while (System.Text.Encoding.ASCII.GetString(b, p, 4) != "data") p += 8 + BitConverter.ToInt32(b, p + 4);
            int n = BitConverter.ToInt32(b, p + 4) / 2; var x = new float[n];
            for (int i = 0; i < n; i++) x[i] = BitConverter.ToInt16(b, p + 8 + 2 * i) / 32768f;
            Console.WriteLine(VoiceDsp.Loudness(x, rate).ToString("0.00", CultureInfo.InvariantCulture));
            return;
        }
        var doc = JsonDocument.Parse(Console.In.ReadToEnd()).RootElement;
        var lines = doc.GetProperty("lines").EnumerateArray().Select(e => new StoryRetime.LineItem
            { id = e.GetProperty("id").GetString(), t = F(e, "t"), maxSec = F(e, "maxSec"), dur = F(e, "dur"), anchor = A(e, "anchor") }).ToArray();
        var items = doc.GetProperty("items").EnumerateArray().Select(e => new StoryRetime.Item { t = F(e, "t"), anchor = A(e, "anchor") }).ToArray();
        var durs = new Dictionary<string, float>();
        foreach (var p in doc.GetProperty("durs").EnumerateObject()) durs[p.Name] = p.Value.GetSingle();
        var da = A(doc, "durationAnchor");
        float duration = F(doc, "duration");
        StoryRetime.InferAnchors(lines, items, ref da, duration);
        float nd = StoryRetime.Core(lines, items, da, duration, id => durs.TryGetValue(id, out var d) ? d : 0f);
        var sb = new StringBuilder("{\"lines\":[");
        sb.Append(string.Join(",", lines.Select(l => string.Format(CultureInfo.InvariantCulture, "{{\"id\":\"{0}\",\"t\":{1:R},\"maxSec\":{2:R}}}", l.id, l.t, l.maxSec))));
        sb.Append("],\"items\":[").Append(string.Join(",", items.Select(i => i.t.ToString("R", CultureInfo.InvariantCulture))));
        sb.Append("],\"duration\":").Append(nd.ToString("R", CultureInfo.InvariantCulture)).Append("}");
        Console.WriteLine(sb.ToString());
    }
}
