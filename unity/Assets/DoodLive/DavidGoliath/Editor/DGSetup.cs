// David & Goliath part of DoodLive > Setup Project (called from DoodLiveSetup). Copies the production roles' outputs
// (assets/david-goliath/**, docs/david-goliath/design/faces) into the Unity project, sets import options, builds the
// two page-coloured materials and the stage prefab (DGDirector + two DGActors with their glTF clips). Everything is
// regenerated from the repo on every Setup; nothing here is hand-edited in the editor. docs/david-goliath/INTEGRATION.md.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using DoodLive.DavidGoliath;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace DoodLive.EditorTools
{
    public static class DGSetup
    {
        public const string Dir = "Assets/DoodLive/DavidGoliath";
        public const string SheetName = "david-goliath-A4";                  // reference image name (prefix "david-goliath")
        public const string SheetPath = Dir + "/Tracking/" + SheetName + ".png";
        // Coloured versions for ARCore image tracking (a blank page scores 0/100 there; these score 90-100). The marker
        // path (SheetFinder) finds any version; these only help when the image path locks first (LESSONS L49).
        public static readonly string[] ColouredSheetPaths = { Dir + "/Tracking/" + SheetName + "-demo.png", Dir + "/Tracking/" + SheetName + "-colored.png" };
        const string Res = Dir + "/Resources/DG";
        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
        static string A(string rel) => Path.Combine(RepoRoot, "assets/david-goliath", rel);

        // ---------------- design.json / clips.json shapes (only the fields used here) ----------------
        [Serializable] class Expr { public string idle, walk, talk, kneel_pick, sling_windup, sling_release, run, victory, pray, taunt, laugh, roar, charge, hit_react, fall, down; }
        [Serializable] class Decal { public Expr clipExpression; public string @default; }
        [Serializable] class Decals { public Decal david, goliath; }
        [Serializable] class Char { public float height, sheetX; }   // sheetX: CONTRACT §11.4 (-0.350 / +0.130)
        [Serializable] class Chars { public Char david, goliath; }
        [Serializable] class Design { public Chars characters; public Decals faceDecals; }

        // =====================================================================================================
        /// <summary>Copy every input; returns false (with an error) when a role's deliverable is missing.</summary>
        public static bool CopyInputs()
        {
            foreach (var d in new[] { "Models", "Faces", "Tracking", "Textures", "Materials", "Data", "Resources/DG/voice/zh", "Resources/DG/voice/en", "Resources/DG/music", "Resources/DG/sfx" })
                Directory.CreateDirectory(Path.Combine(Dir, d));
            var need = new List<(string src, string dst)>
            {
                (A("anim/david.glb"), $"{Dir}/Models/david.glb"),          // anim GLBs = model + skin + 19 clips (ANIMATION.md §1)
                (A("anim/goliath.glb"), $"{Dir}/Models/goliath.glb"),
                (A("model/desert.glb"), $"{Dir}/Models/desert.glb"),        // desert set (CONTRACT §12, Desert role)
                (A("anim/clips.json"), $"{Dir}/Data/clips.json"),
                (A("design.json"), $"{Dir}/Data/design.json"),
                (A("sheet/template.json"), $"{Dir}/Data/template.json"),
                (A("sheet/reference.png"), SheetPath),                       // = print/david-goliath-A4.png (RIG.md §5)
                (A("sheet/demo-sheet.png"), ColouredSheetPaths[0]),            // the design.json demo colouring on the page
                (Path.Combine(RepoRoot, "print/david-goliath-A4-colored.png"), ColouredSheetPaths[1]),   // the bright coloured print
                (A("sheet/demo-colored.png"), $"{Dir}/Textures/dg-demo-colored.png"),
                (A("sheet/demo-sheet.png"), $"{Dir}/Textures/dg-demo-sheet.png"),
                // sand-ground mask fitted to the real print by tools/make_dg_sheet.py (CONTRACT §12.4; Design's
                // docs/david-goliath/design/ground-mask.png left coloured outline specks on the sand)
                (A("sheet/ground-mask.png"), $"{Dir}/Textures/dg-ground-mask.png"),
                (A("timeline.json"), $"{Res}/timeline.json"),
                (A("audio/sfx/mix.json"), $"{Res}/sfx_mix.json"),
                (A("audio/music/cues.json"), $"{Res}/music_cues.json"),
            };
            foreach (var f in Directory.GetFiles(Path.Combine(RepoRoot, "docs/david-goliath/design/faces"), "*.png")) need.Add((f, $"{Dir}/Faces/{Path.GetFileName(f)}"));
            // WAV only (Resources.Load is by name; an .mp3 twin would be ambiguous and double the APK)
            void Wavs(string srcDir, string dstDir)
            {
                var src = Directory.GetFiles(A(srcDir), "*.wav").ToList();
                foreach (var f in src) need.Add((f, $"{dstDir}/{Path.GetFileName(f)}"));
                foreach (var old in Directory.GetFiles(dstDir, "*.wav"))
                    if (!src.Any(s => Path.GetFileName(s) == Path.GetFileName(old))) AssetDatabase.DeleteAsset(old.Replace('\\', '/'));
            }
            Wavs("audio/voice/zh", $"{Res}/voice/zh"); Wavs("audio/voice/en", $"{Res}/voice/en");
            Wavs("audio/music", $"{Res}/music"); Wavs("audio/sfx", $"{Res}/sfx");
            bool ok = true;
            foreach (var (src, dst) in need)
            {
                if (!File.Exists(src)) { Debug.LogError($"DG setup: missing input {src}"); ok = false; continue; }
                if (File.Exists(dst) && File.ReadAllBytes(dst).SequenceEqual(File.ReadAllBytes(src))) continue;
                File.Copy(src, dst, true);
            }
            AssetDatabase.Refresh();
            Debug.Log($"DG setup: {need.Count} inputs checked ({(ok ? "all present" : "SOME MISSING")})");
            return ok;
        }

        /// <summary>The D&amp;G sheet must share the angel sheet's markers and art rectangle, because capture/warp uses one
        /// template (Resources/template.json). Checked here so a sheet change cannot silently break the scan.</summary>
        public static void CheckTemplate(string angelTemplatePath)
        {
            var a = Template.Parse(File.ReadAllText(angelTemplatePath));
            var d = Template.Parse(File.ReadAllText($"{Dir}/Data/template.json"));
            bool same = a.page == d.page && a.art == d.art && Enumerable.Range(0, 4).All(i => a.markers[i] == d.markers[i])
                        && Mathf.Abs(a.ArtAspect - d.ArtAspect) < 1e-3f;
            if (same) Debug.Log($"DG setup: sheet template matches the angel's (art {d.art}, aspect {d.ArtAspect:F4})");
            else Debug.LogError($"DG setup: sheet template differs from the angel's: page {d.page} vs {a.page}, art {d.art} vs {a.art}, aspect {d.ArtAspect} vs {a.ArtAspect}. Capture would warp the wrong rectangle.");
        }

        // ---------------- import options ----------------
        public static void ImportAll(Func<string, bool, int, Texture2D> importTexture)
        {
            importTexture($"{Dir}/Textures/dg-demo-colored.png", false, 1024);
            importTexture($"{Dir}/Textures/dg-demo-sheet.png", false, 2048);
            {   // ground mask: one 8-bit channel, linear (0 / 128 / 255 are codes, not colours), bilinear, no mips
                string mp = $"{Dir}/Textures/dg-ground-mask.png";
                var ti = (TextureImporter)AssetImporter.GetAtPath(mp);
                ti.textureType = TextureImporterType.SingleChannel; ti.sRGBTexture = false; ti.isReadable = false;
                ti.mipmapEnabled = false; ti.npotScale = TextureImporterNPOTScale.None; ti.wrapMode = TextureWrapMode.Clamp;
                ti.filterMode = FilterMode.Bilinear; ti.maxTextureSize = 2048; ti.alphaSource = TextureImporterAlphaSource.None;
                var st = ti.GetDefaultPlatformTextureSettings(); st.format = TextureImporterFormat.R8; st.textureCompression = TextureImporterCompression.Uncompressed;
                ti.SetPlatformTextureSettings(st);
                var an = ti.GetPlatformTextureSettings("Android"); an.overridden = true; an.format = TextureImporterFormat.R8; an.maxTextureSize = 2048;
                ti.SetPlatformTextureSettings(an);
                ti.SaveAndReimport();
            }
            foreach (var f in Directory.GetFiles($"{Dir}/Faces", "*.png"))
            {
                var t = importTexture(f.Replace('\\', '/'), false, 512);
                var ti = (TextureImporter)AssetImporter.GetAtPath(f.Replace('\\', '/'));
                ti.mipmapEnabled = true; ti.alphaIsTransparency = true; ti.wrapMode = TextureWrapMode.Clamp; ti.SaveAndReimport();
            }
            void Audio(string dir, AudioClipLoadType load, float quality)
            {
                foreach (var f in Directory.GetFiles(dir, "*.wav"))
                {
                    var ai = (AudioImporter)AssetImporter.GetAtPath(f.Replace('\\', '/'));
                    var s = ai.defaultSampleSettings;
                    s.loadType = load; s.compressionFormat = AudioCompressionFormat.Vorbis; s.quality = quality;
                    s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate; s.preloadAudioData = load != AudioClipLoadType.Streaming;
                    ai.defaultSampleSettings = s; ai.forceToMono = true; ai.loadInBackground = load == AudioClipLoadType.Streaming;
                    ai.SaveAndReimport();
                }
            }
            Audio($"{Res}/voice/zh", AudioClipLoadType.CompressedInMemory, 0.6f);
            Audio($"{Res}/voice/en", AudioClipLoadType.CompressedInMemory, 0.6f);
            Audio($"{Res}/sfx", AudioClipLoadType.DecompressOnLoad, 0.6f);     // short; must start sample-exact on hits
            Audio($"{Res}/music", AudioClipLoadType.CompressedInMemory, 0.5f);
            foreach (var g in new[] { "david", "goliath", "desert" }) AssetDatabase.ImportAsset($"{Dir}/Models/{g}.glb", ImportAssetOptions.ForceUpdate);
        }

        // ---------------- materials ----------------
        public static Material[] MakeMaterials(Texture2D demo)
        {
            var sh = Shader.Find("DoodLive/DGPaperLit");
            if (!sh) Debug.LogError("DG setup: shader DoodLive/DGPaperLit not found");
            Material Mat(string name)
            {
                string path = $"{Dir}/Materials/{name}.mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (!m) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
                m.shader = sh;
                m.SetTexture("_BaseMap", demo);
                m.SetColor("_BaseColor", new Color(0.97f, 0.95f, 0.90f));   // unpainted = warm paper (design palette paper)
                m.SetFloat("_BaseAmt", 0.9f); m.SetFloat("_Smoothness", 0.25f); m.SetFloat("_Metallic", 0); m.SetFloat("_Rim", 0.2f);
                m.SetFloat("_Cull", (float)UnityEngine.Rendering.CullMode.Back); m.SetFloat("_BackTint", 1); m.SetFloat("_DecalAmt", 1);
                EditorUtility.SetDirty(m);
                return m;
            }
            var desert = Mat("dg_desert");                                // desert.glb: same scan, front-projected UV0 (§12.1), no UV1
            desert.SetTexture("_DecalMap", null); desert.SetFloat("_DecalAmt", 0); desert.SetFloat("_Rim", 0.08f); desert.SetFloat("_Smoothness", 0.1f);
            desert.SetColor("_BaseColor", Hex(0xF3D58E)); desert.SetFloat("_BaseAmt", 1);   // unpainted pieces = sand (§12.4)
            var ground = GroundMaterial(demo);
            var mats = new[] { Mat("dg_david"), Mat("dg_goliath"), desert, ground };
            foreach (var m in mats) { m.SetVector("_AmbTint", AmbTint); EditorUtility.SetDirty(m); }   // linear multiplier (SetVector: no sRGB conversion)
            // order matters: [0] david, [1] goliath, [2] desert, [3] ground; ARColoringController sets _BaseMap on all of them
            return mats;
        }

        /// <summary>Warm the URP SH ambient on the D&amp;G materials only (the scene's trilight ambient is lavender for the
        /// angel; on sand it made the shadows violet). Angel materials and RenderSettings are untouched.</summary>
        public static readonly Vector4 AmbTint = new Vector4(1.06f, 0.97f, 0.84f, 1);
        static Color Hex(int rgb) => new Color(((rgb >> 16) & 255) / 255f, ((rgb >> 8) & 255) / 255f, (rgb & 255) / 255f, 1);

        static Material GroundMaterial(Texture2D demo)
        {
            var sh = Shader.Find("DoodLive/DGGround");
            if (!sh) Debug.LogError("DG setup: shader DoodLive/DGGround not found");
            string path = $"{Dir}/Materials/dg_ground.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!m) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
            m.shader = sh;
            m.SetTexture("_BaseMap", demo);
            var mask = AssetDatabase.LoadAssetAtPath<Texture2D>($"{Dir}/Textures/dg-ground-mask.png");
            if (!mask) Debug.LogError("DG setup: ground mask did not import");
            m.SetTexture("_MaskMap", mask);
            m.SetColor("_SandColor", Hex(0xE3C38C)); m.SetFloat("_Smoothness", 0.05f);
            EditorUtility.SetDirty(m);
            return m;
        }

        static Material WaterMaterial()
        {
            var sh = Shader.Find("DoodLive/DGWater");
            if (!sh) Debug.LogError("DG setup: shader DoodLive/DGWater not found");
            string path = $"{Dir}/Materials/dg_water.mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (!m) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
            m.shader = sh; EditorUtility.SetDirty(m);
            return m;
        }

        // ---------------- stage prefab ----------------
        public static GameObject MakeStagePrefab(Material[] mats)
        {
            var design = JsonUtility.FromJson<Design>(File.ReadAllText($"{Dir}/Data/design.json"));
            var clipInfo = JsonUtility.FromJson<DGClips>(File.ReadAllText($"{Dir}/Data/clips.json"));
            var stage = new GameObject("DavidGoliath");
            var dir = stage.AddComponent<DGDirector>();
            var shake = new GameObject("DGShake").transform; shake.SetParent(stage.transform, false);
            dir.shake = shake;
            dir.davidSheetX = design.characters.david.sheetX; dir.goliathSheetX = design.characters.goliath.sheetX;

            var page = new GameObject("DemoPage"); page.transform.SetParent(stage.transform, false);
            page.AddComponent<MeshFilter>();
            var pr = page.AddComponent<MeshRenderer>();
            string pmPath = $"{Dir}/Materials/dg_demo_page.mat";
            var pm = AssetDatabase.LoadAssetAtPath<Material>(pmPath);
            // DGPaperLit with no paper replacement: the printed page as it is, but lit, so it takes the actors' and the
            // desert's shadows in the demo (an unlit page made everyone float)
            var lit = Shader.Find("DoodLive/DGPaperLit");
            if (!pm) { pm = new Material(lit); AssetDatabase.CreateAsset(pm, pmPath); }
            pm.shader = lit; pm.SetTexture("_BaseMap", AssetDatabase.LoadAssetAtPath<Texture2D>($"{Dir}/Textures/dg-demo-sheet.png")); pm.SetColor("_BaseColor", Color.white);
            pm.SetFloat("_BaseAmt", 0); pm.SetFloat("_Rim", 0); pm.SetFloat("_Smoothness", 0.05f); pm.SetFloat("_Metallic", 0); pm.SetFloat("_DecalAmt", 0);
            pm.SetFloat("_Cull", (float)UnityEngine.Rendering.CullMode.Back); pm.SetFloat("_BackTint", 1);
            EditorUtility.SetDirty(pm);
            pr.sharedMaterial = pm; pr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            dir.demoPage = pr;

            dir.david = MakeActor("david", shake, mats[0], design.characters.david.height, design.faceDecals.david, clipInfo);
            dir.goliath = MakeActor("goliath", shake, mats[1], design.characters.goliath.height, design.faceDecals.goliath, clipInfo);
            MakeDesert(dir, shake, mats[2], WaterMaterial(), clipInfo);
            var ground = new GameObject("Ground"); ground.transform.SetParent(shake, false);   // sand page (§12.4); mesh built by DGDirector
            ground.AddComponent<MeshFilter>();
            var gr = ground.AddComponent<MeshRenderer>(); gr.sharedMaterial = mats[3];
            gr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; gr.receiveShadows = true;
            dir.ground = gr;
            string path = $"{Dir}/DavidGoliath.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(stage, path);
            Object.DestroyImmediate(stage);
            Debug.Log($"DG setup: stage prefab {path}");
            return prefab;
        }

        /// <summary>desert.glb under the shake pivot at the page origin (same axes as the actors: glTFast mirrors X, the
        /// stage maps design x to local -x). Page-coloured material everywhere except the brook film (dg_water).</summary>
        static void MakeDesert(DGDirector dir, Transform parent, Material page, Material water, DGClips info)
        {
            string glb = $"{Dir}/Models/desert.glb";
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(glb);
            if (!model) { Debug.LogError($"DG setup: {glb} did not import (glTFast?)"); return; }
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.transform.SetParent(parent, false);
            inst.transform.localPosition = Vector3.zero; inst.transform.localRotation = Quaternion.identity; inst.transform.localScale = Vector3.one;
            foreach (var an in inst.GetComponentsInChildren<Animator>(true)) Object.DestroyImmediate(an);
            dir.desertAnimator = inst.AddComponent<Animator>();   // banners: DGDirector plays the wave clips through it (clip paths are relative to this root)
            dir.desertAnimator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            dir.desert = inst.transform;
            int nPage = 0, nWater = 0;
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var ms = r.sharedMaterials;
                bool isWater = false;
                for (int i = 0; i < ms.Length; i++)
                {
                    bool w = (ms[i] && ms[i].name.StartsWith("dg_water")) || r.name == "brook";
                    ms[i] = w ? water : page; isWater |= w;
                }
                r.sharedMaterials = ms;
                r.shadowCastingMode = isWater ? UnityEngine.Rendering.ShadowCastingMode.Off : UnityEngine.Rendering.ShadowCastingMode.On;
                r.receiveShadows = !isWater;
                if (r is SkinnedMeshRenderer smr) smr.updateWhenOffscreen = true;
                if (isWater) nWater++; else nPage++;
            }
            dir.desertClips = AssetDatabase.LoadAllAssetsAtPath(glb).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__preview")).OrderBy(c => c.name).ToArray();

            // stones picked up in david_kneel_pick (clips.json desertEvents: "desert/fiveStones/stoneK" at sec)
            var kneel = info.clips.FirstOrDefault(c => c.action == "david_kneel_pick");
            var all = inst.GetComponentsInChildren<Transform>(true);
            var stones = new List<Renderer>(); var hide = new List<float>();
            if (kneel?.desertEvents != null)
                foreach (var e in kneel.desertEvents)
                {
                    string leaf = e.hide.Substring(e.hide.LastIndexOf('/') + 1);
                    var t = all.FirstOrDefault(x => x.name == leaf);
                    var r = t ? t.GetComponentInChildren<Renderer>(true) : null;
                    if (!r) { Debug.LogError($"DG setup: desert has no renderer for {e.hide}"); continue; }
                    stones.Add(r); hide.Add(e.sec);
                }
            else Debug.LogError("DG setup: clips.json david_kneel_pick has no desertEvents");
            dir.desertStones = stones.ToArray(); dir.desertStoneHideSec = hide.ToArray();
            if (kneel?.markers?.pick5 != null && kneel.markers.pick5.sec >= 0) dir.stoneShowSec = kneel.markers.pick5.sec;
            var pieces = new[] { "duneFar", "hillIsrael", "hillPhil", "tentIsrael1", "tentIsrael2", "tentIsrael3", "tentPhil1", "tentPhil2", "tentPhil3",
                                 "bannerIsrael", "bannerPhil", "dune1", "dune2", "dune3", "rockL1", "rockL2", "rockM1", "rockM2", "rockFR1", "rockFR2",
                                 "shrubL", "brook", "fiveStones" };
            foreach (var n in pieces) if (!all.Any(x => x.name == n)) Debug.LogError($"DG setup: desert.glb has no node {n} (CONTRACT §12.2)");
            Debug.Log($"DG setup: desert renderers {nPage} page + {nWater} water, clips [{dir.desertClips.Length}] {string.Join(" ", dir.desertClips.Select(c => $"{c.name}({c.length:F2}s)"))}, " +
                      $"stones {stones.Count} hide at [{string.Join(", ", hide.Select(h => h.ToString("F3")))}] s, own stone from {dir.stoneShowSec:F3} s");
        }

        static readonly string[] Clips = { "idle", "walk", "talk", "kneel_pick", "sling_windup", "sling_release", "run", "victory", "pray",
                                           "taunt", "laugh", "roar", "charge", "hit_react", "fall", "down" };   // CONTRACT §5

        static DGActor MakeActor(string id, Transform parent, Material mat, float height, Decal decal, DGClips info)
        {
            string glb = $"{Dir}/Models/{id}.glb";
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(glb);
            if (!model) { Debug.LogError($"DG setup: {glb} did not import (glTFast?)"); return null; }
            var go = new GameObject(char.ToUpper(id[0]) + id.Substring(1)); go.transform.SetParent(parent, false);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.name = "model"; inst.transform.SetParent(go.transform, false);
            var actor = go.AddComponent<DGActor>();
            actor.id = id; actor.height = height; actor.material = mat;
            actor.animator = inst.GetComponent<Animator>() ?? inst.AddComponent<Animator>();
            actor.animator.runtimeAnimatorController = null; actor.animator.applyRootMotion = false;
            actor.animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;

            var all = AssetDatabase.LoadAllAssetsAtPath(glb).OfType<AnimationClip>().Where(c => c.name.StartsWith(id + "_")).OrderBy(c => c.name).ToArray();
            actor.clips = all;
            actor.loops = all.Select(c => info.clips.FirstOrDefault(x => x.action == c.name)?.loop ?? false).ToArray();
            string names = string.Join(" ", all.Select(c => $"{c.name.Substring(id.Length + 1)}({c.length:F2}s{(actor.loops[Array.IndexOf(all, c)] ? ",loop" : "")})"));
            Debug.Log($"DG setup: {id} clips [{all.Length}] {names}");
            var expect = id == "david" ? Clips.Take(9) : Clips.Skip(9).Prepend("talk").Prepend("walk").Prepend("idle");
            foreach (var n in expect) if (!all.Any(c => c.name == $"{id}_{n}")) Debug.LogError($"DG setup: {glb} has no clip {id}_{n} (CONTRACT §5)");
            foreach (var c in all) if (Math.Abs(c.length - (info.clips.FirstOrDefault(x => x.action == c.name)?.seconds ?? c.length)) > 0.05f)
                    Debug.LogWarning($"DG setup: {c.name} is {c.length:F3} s in Unity, clips.json says {info.clips.First(x => x.action == c.name).seconds}");

            // faces: design.json faceDecals.<id>.clipExpression -> Faces/<id>_<expr>.png
            Texture2D Face(string expr) => string.IsNullOrEmpty(expr) ? null : AssetDatabase.LoadAssetAtPath<Texture2D>($"{Dir}/Faces/{id}_{expr}.png");
            actor.defaultFace = Face(decal.@default);
            actor.faces = all.Select(c => Face((string)typeof(Expr).GetField(c.name.Substring(id.Length + 1))?.GetValue(decal.clipExpression)) ?? actor.defaultFace).ToArray();
            if (!actor.defaultFace) Debug.LogError($"DG setup: no default face decal for {id}");
            mat.SetTexture("_DecalMap", actor.defaultFace);

            int rcount = 0;
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var ms = r.sharedMaterials; for (int i = 0; i < ms.Length; i++) ms[i] = mat;   // dg_page -> page-coloured
                r.sharedMaterials = ms; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On; rcount++;
                if (r is SkinnedMeshRenderer smr) smr.updateWhenOffscreen = true;
                if (r.name.Contains("stone")) actor.stone = r;
            }
            var bones = inst.GetComponentsInChildren<Transform>(true).Select(t => t.name).ToHashSet();
            foreach (var b in new[] { "root", "hips", "head", "jaw", "handR", "footL", "footR" }) if (!bones.Contains(b)) Debug.LogError($"DG setup: {id} has no bone {b}");
            Debug.Log($"DG setup: {id} renderers {rcount}, stone {(actor.stone ? actor.stone.name : "-")}, faces {actor.faces.Count(f => f)}/{all.Length}");
            return actor;
        }
    }
}
