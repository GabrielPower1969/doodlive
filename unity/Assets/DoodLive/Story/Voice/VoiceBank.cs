// VoiceBank: which voice clip plays for a story line (docs/VOICE-SYSTEM.md). Resolution per line, first hit wins:
//   1. the casting's choice for this line, then for this line's role   (voices/<story>/<lang>/casting.json)
//   2. "mine": the family's own recordings made on this device         (voices/<story>/<lang>/mine/)
//   3. the casting's default pack (an imported or downloaded pack)     (voices/<story>/<lang>/<pack>/)
//   4. the bundled default in the APK                                   (Resources/Stories/<story>/voice/<lang>/<line>)
//   5. nothing: the subtitle shows for the baked slot, the play keeps its baked timing.
// A casting choice of "bundled" jumps straight to 4 (put one line back to the original, keep the other recordings).
//
// Everything under voices/ lives in Application.persistentDataPath and never leaves the device unless a parent exports
// a pack (ExportZip -> share sheet). Device files load asynchronously (UnityWebRequestMultimedia), so call
// Prepare(story, lang) early (sheet identified, home screen) and Resolve() when the play starts: a VoiceCast is a frozen
// snapshot, so the clip that plays and the duration the timeline was re-timed to always agree.
#pragma warning disable 0649   // fields filled by JsonUtility
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Networking;
using Object = UnityEngine.Object;

namespace DoodLive.Story
{
    // ---------------- voice pack manifest: voicepack.json (same file in a pack folder, a zip and the repo) ----------------
    [Serializable] public class VoiceSpeaker { public string id, name, role; public bool minor; }
    [Serializable] public class VoiceConsent
    {
        public string by, date, scope = "device";   // by: who agreed (the parent); scope: "device" | "family-share" | "public"
        public bool minors, parentConfirmed;         // minors: a child's voice is in this pack
    }
    [Serializable] public class VoiceLine
    {
        public string id, file, role, speaker, source;   // source: "tts:<engine>:<voice>", "own:<session>", "studio:<who>"
        public float sec, lufs, peak;                    // seconds, integrated LUFS, sample peak dBFS (after import)
    }
    [Serializable] public class VoicePack
    {
        public string format = "doodlive-voicepack";
        public int formatVersion = 1;
        public string id, story, lang, title, kind, licence, created, tool;   // kind: "tts" | "family" | "studio"
        public int storyVersion;
        public float targetLufs = -17f;
        public VoiceConsent consent;
        public VoiceSpeaker[] speakers;
        public VoiceLine[] lines;
        [NonSerialized] public string dir;                                   // folder on device (not in the file)
        public VoiceLine Line(string lineId) => lines?.FirstOrDefault(l => l.id == lineId);
    }

    // ---------------- casting: which pack speaks which role / line ----------------
    [Serializable] public class VoiceChoice { public string key, pack; }    // key = role id or line id
    [Serializable] public class VoiceCasting
    {
        public string @default = "";                 // "" = mine, then bundled
        public VoiceChoice[] roles = new VoiceChoice[0], lines = new VoiceChoice[0];
        public string For(VoiceChoice[] list, string key) => list?.FirstOrDefault(c => c.key == key)?.pack;
    }

    /// <summary>One play's frozen voice set: the clip each line plays and its length (for StoryRetime).</summary>
    public class VoiceCast
    {
        public readonly string story, lang;
        readonly Dictionary<string, AudioClip> clips = new Dictionary<string, AudioClip>();
        readonly Dictionary<string, string> sources = new Dictionary<string, string>();
        internal VoiceCast(string story, string lang) { this.story = story; this.lang = lang; }
        internal void Set(string line, AudioClip c, string source) { clips[line] = c; sources[line] = source; }
        public AudioClip Clip(string line) => clips.TryGetValue(line, out var c) ? c : null;
        /// <summary>Clip length in seconds, 0 when the line has no clip (StoryRetime keeps the baked slot).</summary>
        public float Duration(string line) { var c = Clip(line); return c ? c.length : 0f; }
        /// <summary>"bundled", "mine", a pack id, or "none".</summary>
        public string Source(string line) => sources.TryGetValue(line, out var s) ? s : "none";
        public int Count(string source) => sources.Values.Count(s => s == source);
    }

    public static class VoiceBank
    {
        public const string Mine = "mine", Bundled = "bundled", ManifestName = "voicepack.json";
        public const float TargetLufs = -17f, PeakDb = -1.5f;   // the "natural" chain's target (LESSONS L50)
        const long MaxZipBytes = 200L * 1024 * 1024; const int MaxZipEntries = 600;
        static readonly Regex SafeId = new Regex("^[a-z0-9][a-z0-9_-]{0,63}$");
        static readonly Regex SafeFile = new Regex("^[A-Za-z0-9_-]{1,64}\\.(wav|ogg)$");

        public static string Root => Path.Combine(Application.persistentDataPath, "voices");
        public static string LangDir(string story, string lang) => Path.Combine(Root, story, lang);
        public static string PackDir(string story, string lang, string pack) => Path.Combine(LangDir(story, lang), pack);

        static readonly Dictionary<string, AudioClip> fileClips = new Dictionary<string, AudioClip>();   // full path -> clip
        static readonly HashSet<string> loading = new HashSet<string>(), ready = new HashSet<string>();  // "<story>/<lang>"

        // ---------------- packs on the device ----------------
        /// <summary>Installed packs for one story + language ("mine" included when it has lines).</summary>
        public static List<VoicePack> Installed(string story, string lang)
        {
            var r = new List<VoicePack>();
            string d = LangDir(story, lang);
            if (!Directory.Exists(d)) return r;
            foreach (var p in Directory.GetDirectories(d))
            {
                var vp = ReadPack(p, story, lang);
                if (vp != null && vp.lines != null && vp.lines.Length > 0) r.Add(vp);
            }
            return r;
        }

        /// <summary>Read a pack folder. A folder without voicepack.json (WAVs dropped in by hand) counts as a pack whose
        /// lines are the file names.</summary>
        public static VoicePack ReadPack(string dir, string story = null, string lang = null)
        {
            if (!Directory.Exists(dir)) return null;
            VoicePack vp = null;
            string mf = Path.Combine(dir, ManifestName);
            try { if (File.Exists(mf)) vp = JsonUtility.FromJson<VoicePack>(File.ReadAllText(mf)); }
            catch (Exception e) { Debug.LogWarning($"VoiceBank: bad manifest {mf}: {e.Message}"); }
            if (vp == null)
            {
                vp = new VoicePack { id = Path.GetFileName(dir), story = story, lang = lang, kind = "family", licence = "private" };
                vp.lines = Directory.GetFiles(dir).Where(f => SafeFile.IsMatch(Path.GetFileName(f)))
                    .Select(f => new VoiceLine { id = Path.GetFileNameWithoutExtension(f), file = Path.GetFileName(f) }).ToArray();
            }
            vp.dir = dir;
            return vp;
        }

        public static VoiceCasting GetCasting(string story, string lang)
        {
            string f = Path.Combine(LangDir(story, lang), "casting.json");
            try { if (File.Exists(f)) return JsonUtility.FromJson<VoiceCasting>(File.ReadAllText(f)) ?? new VoiceCasting(); }
            catch (Exception e) { Debug.LogWarning($"VoiceBank: bad casting {f}: {e.Message}"); }
            return new VoiceCasting();
        }

        public static void SetCasting(string story, string lang, VoiceCasting c)
        {
            Directory.CreateDirectory(LangDir(story, lang));
            File.WriteAllText(Path.Combine(LangDir(story, lang), "casting.json"), JsonUtility.ToJson(c, true));
            ready.Remove(story + "/" + lang);                      // new choices may need files loaded
        }

        // ---------------- async loading ----------------
        class Runner : MonoBehaviour { }
        static Runner runner;
        static MonoBehaviour Host
        {
            get
            {
                if (runner) return runner;
                var go = new GameObject("VoiceBank") { hideFlags = HideFlags.HideAndDontSave };
                if (Application.isPlaying) Object.DontDestroyOnLoad(go);
                return runner = go.AddComponent<Runner>();
            }
        }

        public static bool IsReady(string story, string lang) => ready.Contains(story + "/" + lang);

        /// <summary>Start loading every device clip this story + language may need. Safe to call repeatedly.</summary>
        public static void Prepare(string story, string lang, Action done = null)
        {
            string key = story + "/" + lang;
            if (ready.Contains(key)) { done?.Invoke(); return; }
            if (!Application.isPlaying) { ready.Add(key); done?.Invoke(); return; }
            if (loading.Contains(key)) { if (done != null) Host.StartCoroutine(WaitReady(key, done)); return; }
            loading.Add(key);
            Host.StartCoroutine(LoadAll(story, lang, key, done));
        }

        static IEnumerator WaitReady(string key, Action done) { while (!ready.Contains(key)) yield return null; done(); }

        static IEnumerator LoadAll(string story, string lang, string key, Action done)
        {
            var c = GetCasting(story, lang);
            var want = new HashSet<string> { Mine };
            if (!string.IsNullOrEmpty(c.@default)) want.Add(c.@default);
            foreach (var ch in (c.roles ?? new VoiceChoice[0]).Concat(c.lines ?? new VoiceChoice[0])) if (!string.IsNullOrEmpty(ch.pack)) want.Add(ch.pack);
            want.Remove(Bundled);
            foreach (var pack in want)
            {
                var vp = ReadPack(PackDir(story, lang, pack), story, lang);
                if (vp?.lines == null) continue;
                foreach (var l in vp.lines)
                {
                    if (string.IsNullOrEmpty(l.file) || !SafeFile.IsMatch(l.file)) continue;
                    string f = Path.Combine(vp.dir, l.file);
                    if (fileClips.ContainsKey(f) || !File.Exists(f)) continue;
                    var type = f.EndsWith(".ogg", StringComparison.OrdinalIgnoreCase) ? AudioType.OGGVORBIS : AudioType.WAV;
                    using (var req = UnityWebRequestMultimedia.GetAudioClip(new Uri(f).AbsoluteUri, type))
                    {
                        yield return req.SendWebRequest();
                        if (req.result != UnityWebRequest.Result.Success) { Debug.LogWarning($"VoiceBank: cannot load {f}: {req.error}"); continue; }
                        var clip = DownloadHandlerAudioClip.GetContent(req);
                        if (clip) { clip.name = $"{pack}/{l.id}"; fileClips[f] = clip; }
                    }
                }
            }
            loading.Remove(key); ready.Add(key);
            Debug.Log($"VoiceBank {key}: ready ({fileClips.Count} device clips in memory)");
            done?.Invoke();
        }

        /// <summary>Unload device clips of one story (leaving the story, low memory).</summary>
        public static void Release(string story)
        {
            string prefix = Path.Combine(Root, story) + Path.DirectorySeparatorChar;
            foreach (var k in fileClips.Keys.Where(k => k.StartsWith(prefix)).ToList()) { if (fileClips[k]) Object.Destroy(fileClips[k]); fileClips.Remove(k); }
            ready.RemoveWhere(k => k.StartsWith(story + "/"));
        }

        // ---------------- resolution ----------------
        [Serializable] class TLine { public string id, who, voice; }
        [Serializable] class TLines { public TLine[] lines; }

        /// <summary>Freeze the voice set for one play. timelineJson supplies line ids and roles (voice, else who).
        /// Device clips that have not finished loading are skipped (the next candidate plays), so clip and duration agree.
        /// bundledDir = the Resources folder holding voice/&lt;lang&gt;/ (default "Stories/&lt;story&gt;/").</summary>
        public static VoiceCast Resolve(string story, string lang, string timelineJson, string bundledDir = null)
        {
            bundledDir = bundledDir ?? $"Stories/{story}/";        // David & Goliath: "DG/"
            var cast = new VoiceCast(story, lang);
            var tl = JsonUtility.FromJson<TLines>(timelineJson);
            var casting = GetCasting(story, lang);
            var packs = new Dictionary<string, VoicePack>();
            VoicePack P(string id) { if (!packs.TryGetValue(id, out var p)) packs[id] = p = ReadPack(PackDir(story, lang, id), story, lang); return p; }
            AudioClip FromPack(string id, string line)
            {
                var vl = P(id)?.Line(line);
                if (vl == null || string.IsNullOrEmpty(vl.file)) return null;
                return fileClips.TryGetValue(Path.Combine(P(id).dir, vl.file), out var c) ? c : null;
            }
            foreach (var l in tl?.lines ?? new TLine[0])
            {
                string role = string.IsNullOrEmpty(l.voice) ? l.who : l.voice;
                var order = new List<string>();
                foreach (var explicitPick in new[] { casting.For(casting.lines, l.id), casting.For(casting.roles, role) })
                    if (!string.IsNullOrEmpty(explicitPick)) order.Add(explicitPick);
                order.Add(Mine);
                if (!string.IsNullOrEmpty(casting.@default)) order.Add(casting.@default);
                AudioClip clip = null; string src = "none";
                foreach (var pack in order)
                {
                    if (pack == Bundled) break;
                    clip = FromPack(pack, l.id);
                    if (clip) { src = pack; break; }
                }
                if (!clip) { clip = Resources.Load<AudioClip>($"{bundledDir}voice/{lang}/{l.id}"); if (clip) src = Bundled; }
                cast.Set(l.id, clip, src);
            }
            int n = tl?.lines?.Length ?? 0;
            Debug.Log($"VoiceBank {story}/{lang}: {n} lines, {cast.Count(Bundled)} bundled, {cast.Count(Mine)} mine, {cast.Count("none")} missing, {n - cast.Count(Bundled) - cast.Count(Mine) - cast.Count("none")} from packs" + (IsReady(story, lang) ? "" : " (device clips still loading)"));
            return cast;
        }

        /// <summary>For StoryRetime.Load: installed clip length per line (0 = keep the baked slot).</summary>
        public static Func<string, float> Durations(VoiceCast cast) => cast != null ? (Func<string, float>)cast.Duration : null;

        // ---------------- in-app recording ("mine") ----------------
        /// <summary>A parent's consent must be on file before a recording is saved (docs/VOICE-SYSTEM.md section 8).</summary>
        public static void RecordConsent(string story, string lang, string by, bool minors)
        {
            var vp = ReadPack(PackDir(story, lang, Mine), story, lang) ?? new VoicePack { id = Mine, story = story, lang = lang, lines = new VoiceLine[0] };
            vp.id = Mine; vp.story = story; vp.lang = lang; vp.kind = "family"; vp.licence = "private-family";
            vp.consent = new VoiceConsent { by = by, minors = minors, parentConfirmed = true, scope = "device", date = DateTime.UtcNow.ToString("yyyy-MM-dd") };
            WritePack(vp, PackDir(story, lang, Mine));
        }

        public static bool HasConsent(string story, string lang)
            => ReadPack(PackDir(story, lang, Mine), story, lang)?.consent?.parentConfirmed == true;

        /// <summary>Save one recorded take as this device's voice for a line: trim, level (-17 LUFS, peak &lt;= -1.5 dBFS,
        /// no compression), 16-bit WAV in voices/&lt;story&gt;/&lt;lang&gt;/mine/. Returns false without consent.</summary>
        public static bool SaveRecording(string story, string lang, string lineId, string role, string speaker, float[] mono, int rate)
        {
            if (!HasConsent(story, lang)) { Debug.LogWarning("VoiceBank: no parental consent on file; recording not saved"); return false; }
            if (!SafeFile.IsMatch(lineId + ".wav")) return false;
            var x = VoiceDsp.Trim(mono, rate);
            float lufs = VoiceDsp.Loudness(x, rate);
            float gainDb = float.IsNegativeInfinity(lufs) ? 0 : TargetLufs - lufs;
            float peak = VoiceDsp.PeakDb(x);
            gainDb = Mathf.Min(gainDb, PeakDb - peak);                 // never clip; a quiet, spiky take ends up a bit softer
            VoiceDsp.Gain(x, gainDb);
            string dir = PackDir(story, lang, Mine); Directory.CreateDirectory(dir);
            string file = lineId + ".wav", path = Path.Combine(dir, file);
            VoiceDsp.WriteWav(path, x, rate);
            var vp = ReadPack(dir, story, lang);
            var lines = (vp.lines ?? new VoiceLine[0]).Where(l => l.id != lineId).ToList();
            lines.Add(new VoiceLine { id = lineId, file = file, role = role, speaker = speaker, source = "own:device",
                                      sec = x.Length / (float)rate, lufs = VoiceDsp.Loudness(x, rate), peak = VoiceDsp.PeakDb(x) });
            vp.lines = lines.ToArray();
            WritePack(vp, dir);
            if (fileClips.TryGetValue(path, out var old)) { if (old) Object.Destroy(old); fileClips.Remove(path); }
            var clip = AudioClip.Create($"{Mine}/{lineId}", x.Length, 1, rate, false); clip.SetData(x, 0);
            fileClips[path] = clip;                                    // usable at once, no reload
            return true;
        }

        public static void DeleteRecording(string story, string lang, string lineId)
        {
            string dir = PackDir(story, lang, Mine);
            var vp = ReadPack(dir, story, lang); if (vp?.lines == null) return;
            foreach (var l in vp.lines.Where(l => l.id == lineId))
            {
                string f = Path.Combine(dir, l.file);
                if (fileClips.TryGetValue(f, out var c)) { if (c) Object.Destroy(c); fileClips.Remove(f); }
                if (File.Exists(f)) File.Delete(f);
            }
            vp.lines = vp.lines.Where(l => l.id != lineId).ToArray();
            WritePack(vp, dir);
        }

        /// <summary>Delete an installed pack (or all of "mine") from the device.</summary>
        public static void DeletePack(string story, string lang, string pack)
        {
            string dir = PackDir(story, lang, pack);
            foreach (var k in fileClips.Keys.Where(k => k.StartsWith(dir + Path.DirectorySeparatorChar)).ToList()) { if (fileClips[k]) Object.Destroy(fileClips[k]); fileClips.Remove(k); }
            if (Directory.Exists(dir)) Directory.Delete(dir, true);
        }

        static void WritePack(VoicePack vp, string dir)
        {
            Directory.CreateDirectory(dir);
            vp.tool = "DoodLive " + Application.version;
            File.WriteAllText(Path.Combine(dir, ManifestName), JsonUtility.ToJson(vp, true));
        }

        // ---------------- import / export (zip through the share sheet or Files) ----------------
        /// <summary>Zip one pack (manifest + clips) to outPath. The UI hands the file to the share sheet; nothing is uploaded.</summary>
        public static string ExportZip(string story, string lang, string pack, string outPath)
        {
            var vp = ReadPack(PackDir(story, lang, pack), story, lang);
            if (vp?.lines == null || vp.lines.Length == 0) throw new InvalidOperationException($"no voices in {story}/{lang}/{pack}");
            if (File.Exists(outPath)) File.Delete(outPath);
            using (var z = ZipFile.Open(outPath, ZipArchiveMode.Create))
            {
                var mf = z.CreateEntry(ManifestName);
                using (var w = new StreamWriter(mf.Open())) w.Write(JsonUtility.ToJson(vp, true));
                foreach (var l in vp.lines)
                {
                    string f = Path.Combine(vp.dir, l.file ?? "");
                    if (SafeFile.IsMatch(l.file ?? "") && File.Exists(f)) z.CreateEntryFromFile(f, l.file, System.IO.Compression.CompressionLevel.Optimal);
                }
            }
            return outPath;
        }

        /// <summary>Install a voice pack zip. Flat archive only: voicepack.json + &lt;name&gt;.wav/.ogg; anything else is
        /// refused. Installs into voices/&lt;story&gt;/&lt;lang&gt;/&lt;id&gt;/ (an existing pack with that id is replaced).
        /// "mine" cannot be overwritten by an import (imported family packs keep their own id).</summary>
        public static VoicePack ImportZip(string zipPath, out string error)
        {
            error = null;
            try
            {
                using (var z = ZipFile.OpenRead(zipPath))
                {
                    if (z.Entries.Count > MaxZipEntries) { error = "too many files"; return null; }
                    if (z.Entries.Sum(e => e.Length) > MaxZipBytes) { error = "too large"; return null; }
                    var me = z.GetEntry(ManifestName); if (me == null) { error = "no voicepack.json"; return null; }
                    VoicePack vp; using (var r = new StreamReader(me.Open())) vp = JsonUtility.FromJson<VoicePack>(r.ReadToEnd());
                    if (vp == null || vp.format != "doodlive-voicepack") { error = "not a DoodLive voice pack"; return null; }
                    if (vp.formatVersion > 1) { error = "made by a newer app version"; return null; }
                    foreach (var s in new[] { vp.id, vp.story, vp.lang }) if (s == null || !SafeId.IsMatch(s)) { error = "bad id/story/lang"; return null; }
                    if (vp.id == Mine || vp.id == Bundled) { error = "reserved pack id"; return null; }
                    foreach (var e in z.Entries)
                        if (e.FullName != ManifestName && !SafeFile.IsMatch(e.FullName)) { error = "unexpected file " + e.FullName; return null; }
                    string dst = PackDir(vp.story, vp.lang, vp.id), tmp = dst + ".importing";
                    if (Directory.Exists(tmp)) Directory.Delete(tmp, true);
                    Directory.CreateDirectory(tmp);
                    foreach (var e in z.Entries) e.ExtractToFile(Path.Combine(tmp, e.FullName), true);
                    DeletePack(vp.story, vp.lang, vp.id);
                    Directory.Move(tmp, dst);
                    ready.Remove(vp.story + "/" + vp.lang);
                    vp.dir = dst;
                    return vp;
                }
            }
            catch (Exception ex) { error = ex.Message; return null; }
        }
    }

    /// <summary>Small, allocation-light DSP for recordings made on the device: trim, BS.1770 loudness, gain, WAV.</summary>
    public static class VoiceDsp
    {
        /// <summary>Trim silence below -45 dBFS at both ends, keep 30 ms before and 60 ms after (voice.py TRIM + PAD).</summary>
        public static float[] Trim(float[] x, int rate)
        {
            float th = Mathf.Pow(10, -45 / 20f); int a = 0, b = x.Length - 1;
            while (a < x.Length && Mathf.Abs(x[a]) < th) a++;
            while (b > a && Mathf.Abs(x[b]) < th) b--;
            if (a >= x.Length) return new float[0];
            a = Mathf.Max(0, a - (int)(0.03f * rate)); b = Mathf.Min(x.Length - 1, b + (int)(0.06f * rate));
            var y = new float[b - a + 1]; Array.Copy(x, a, y, 0, y.Length);
            int f = Mathf.Min(y.Length / 2, (int)(0.006f * rate));   // 6 ms fades, no clicks
            for (int i = 0; i < f; i++) { float g = i / (float)f; y[i] *= g; y[y.Length - 1 - i] *= g; }
            return y;
        }

        public static float PeakDb(float[] x) { float p = 1e-9f; foreach (var v in x) p = Mathf.Max(p, Mathf.Abs(v)); return 20 * Mathf.Log10(p); }

        public static void Gain(float[] x, float db) { float g = Mathf.Pow(10, db / 20f); for (int i = 0; i < x.Length; i++) x[i] *= g; }

        /// <summary>Integrated loudness (LUFS), ITU-R BS.1770-4: K-weighting, 400 ms blocks at 75 % overlap,
        /// -70 LUFS absolute and -10 LU relative gates. Mono.</summary>
        public static float Loudness(float[] x, int rate)
        {
            var k = (float[])x.Clone();
            Biquad(k, Shelf(rate)); Biquad(k, HighPass(rate));
            int blk = (int)(0.4 * rate), hop = blk / 4;
            if (k.Length < blk) blk = hop = k.Length;
            if (blk == 0) return float.NegativeInfinity;
            var ms = new List<double>();
            for (int s = 0; s + blk <= k.Length; s += hop) { double z = 0; for (int i = s; i < s + blk; i++) z += k[i] * k[i]; ms.Add(z / blk); }
            double L(double m) => -0.691 + 10 * Math.Log10(Math.Max(m, 1e-12));
            var g1 = ms.Where(m => L(m) > -70).ToList(); if (g1.Count == 0) return float.NegativeInfinity;
            double rel = L(g1.Average()) - 10;
            var g2 = g1.Where(m => L(m) > rel).ToList();
            return (float)L((g2.Count > 0 ? g2 : g1).Average());
        }

        // RBJ-style designs of the two BS.1770 K-weighting stages for any sample rate (match the 48 kHz table values).
        static double[] Shelf(int fs)
        {
            double f0 = 1681.974450955533, G = 3.999843853973347, Q = 0.7071752369554196;
            double K = Math.Tan(Math.PI * f0 / fs), Vh = Math.Pow(10, G / 20), Vb = Math.Pow(Vh, 0.4996667741545416);
            double a0 = 1 + K / Q + K * K;
            return new[] { (Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0 };
        }
        static double[] HighPass(int fs)
        {
            double f0 = 38.13547087602444, Q = 0.5003270373238773, K = Math.Tan(Math.PI * f0 / fs);
            double a0 = 1 + K / Q + K * K;
            return new[] { 1.0, -2.0, 1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0 };
        }
        static void Biquad(float[] x, double[] c)   // c = b0 b1 b2 a1 a2 (a0 = 1)
        {
            double z1 = 0, z2 = 0;
            for (int i = 0; i < x.Length; i++)
            {
                double v = x[i], y = c[0] * v + z1;
                z1 = c[1] * v - c[3] * y + z2; z2 = c[2] * v - c[4] * y;
                x[i] = (float)y;
            }
        }

        /// <summary>16-bit PCM mono WAV.</summary>
        public static void WriteWav(string path, float[] x, int rate)
        {
            using (var w = new BinaryWriter(File.Create(path)))
            {
                int bytes = x.Length * 2;
                w.Write(new[] { 'R', 'I', 'F', 'F' }); w.Write(36 + bytes); w.Write(new[] { 'W', 'A', 'V', 'E' });
                w.Write(new[] { 'f', 'm', 't', ' ' }); w.Write(16); w.Write((short)1); w.Write((short)1);
                w.Write(rate); w.Write(rate * 2); w.Write((short)2); w.Write((short)16);
                w.Write(new[] { 'd', 'a', 't', 'a' }); w.Write(bytes);
                foreach (var v in x) w.Write((short)Mathf.Clamp(Mathf.RoundToInt(v * 32767f), -32768, 32767));
            }
        }
    }
}
