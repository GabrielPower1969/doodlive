// Imports every story pack that uses the generic engine (assets/stories.json, engine "story") into Unity:
//   assets/<id>/anim/<cast>.glb (model + skin + clips), anim/clips.json, model/<set>.glb, pack.json (tools/story/pack.py),
//   sheet/{reference,demo-sheet,demo-colored}.png, docs/<id>/design/faces/*.png, timeline + audio
// -> Assets/DoodLive/Stories/<id>/... and Resources/Stories/<id>/..., materials, and a stage prefab with a StoryDirector.
// Called from DoodLiveSetup.Setup (docs/STORY-ARCHITECTURE.md). Never hand-edit what it generates.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using DoodLive.DavidGoliath;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace DoodLive.Story.EditorTools
{
    public static class StorySetup
    {
        [Serializable] class Reg { public Entry[] stories; }
        [Serializable] public class Entry { public string id, engine, title_zh, title_en, set; public string[] sheets, cast; public int order; }
        [Serializable] class ClipFace { public string clip, face; }
        [Serializable] class CastInfo { public string id, defaultFace; public float height, sheetX; public ClipFace[] clipFaces; }
        [Serializable] class Pack { public string id, set, titleZh, titleEn, setUnpainted; public string[] sheets; public CastInfo[] cast; }

        public class Result
        {
            public Entry entry; public GameObject prefab; public List<string> trackingSheets = new List<string>();
        }

        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
        public static string Dir(string id) => $"Assets/DoodLive/Stories/{id}";
        static string Res(string id) => $"Assets/DoodLive/Stories/{id}/Resources/Stories/{id}";

        public static List<Entry> Registry()
        {
            var reg = JsonUtility.FromJson<Reg>(File.ReadAllText(Path.Combine(RepoRoot, "assets/stories.json")));
            return reg.stories.Where(s => s.engine == "story").OrderBy(s => s.order).ToList();
        }

        /// <summary>Copy, import and build every generic pack. A pack whose inputs are incomplete is skipped with errors.</summary>
        public static List<Result> SetupAll(Func<string, bool, int, Texture2D> importTexture)
        {
            var results = new List<Result>();
            foreach (var e in Registry())
            {
                try
                {
                    var r = Setup(e, importTexture);
                    if (r != null) results.Add(r);
                }
                catch (Exception ex) { Debug.LogError($"Story setup {e.id}: {ex}"); }
            }
            return results;
        }

        static Result Setup(Entry e, Func<string, bool, int, Texture2D> importTexture)
        {
            string id = e.id, dir = Dir(id), res = Res(id), src = Path.Combine(RepoRoot, "assets", id);
            foreach (var d in new[] { "Models", "Faces", "Tracking", "Textures", "Materials", "Data" }) Directory.CreateDirectory(Path.Combine(dir, d));
            foreach (var d in new[] { "voice/zh", "voice/en", "music", "sfx" }) Directory.CreateDirectory(Path.Combine(res, d));
            var pack = JsonUtility.FromJson<Pack>(File.ReadAllText(Path.Combine(src, "pack.json")));
            var need = new List<(string from, string to)>();
            foreach (var c in pack.cast) need.Add((Path.Combine(src, "anim", c.id + ".glb"), $"{dir}/Models/{c.id}.glb"));
            if (!string.IsNullOrEmpty(pack.set)) need.Add((Path.Combine(src, "model", pack.set + ".glb"), $"{dir}/Models/{pack.set}.glb"));
            need.Add((Path.Combine(src, "anim/clips.json"), $"{dir}/Data/clips.json"));
            need.Add((Path.Combine(src, "sheet/reference.png"), $"{dir}/Tracking/{id}-A4.png"));
            need.Add((Path.Combine(src, "sheet/demo-sheet.png"), $"{dir}/Tracking/{id}-A4-demo.png"));
            need.Add((Path.Combine(src, "sheet/demo-colored.png"), $"{dir}/Textures/{id}-demo-colored.png"));
            need.Add((Path.Combine(src, "sheet/demo-sheet.png"), $"{dir}/Textures/{id}-demo-sheet.png"));
            need.Add((Path.Combine(src, "timeline.json"), $"{res}/timeline.json"));
            need.Add((Path.Combine(src, "audio/sfx/mix.json"), $"{res}/sfx_mix.json"));
            need.Add((Path.Combine(src, "audio/music/cues.json"), $"{res}/music_cues.json"));
            string faces = Path.Combine(RepoRoot, "docs", id, "design", "faces");
            if (Directory.Exists(faces)) foreach (var f in Directory.GetFiles(faces, "*.png")) need.Add((f, $"{dir}/Faces/{Path.GetFileName(f)}"));
            void Wavs(string sub, string dst)
            {
                string s = Path.Combine(src, sub); if (!Directory.Exists(s)) { Debug.LogError($"Story setup {id}: no {sub}"); return; }
                var list = Directory.GetFiles(s, "*.wav").ToList();
                foreach (var f in list) need.Add((f, $"{dst}/{Path.GetFileName(f)}"));
                foreach (var old in Directory.GetFiles(dst, "*.wav")) if (!list.Any(x => Path.GetFileName(x) == Path.GetFileName(old))) AssetDatabase.DeleteAsset(old.Replace('\\', '/'));
            }
            Wavs("audio/voice/zh", $"{res}/voice/zh"); Wavs("audio/voice/en", $"{res}/voice/en");
            Wavs("audio/music", $"{res}/music"); Wavs("audio/sfx", $"{res}/sfx");
            bool ok = true;
            foreach (var (from, to) in need)
            {
                if (!File.Exists(from)) { Debug.LogError($"Story setup {id}: missing input {from}"); ok = false; continue; }
                if (File.Exists(to) && File.ReadAllBytes(to).SequenceEqual(File.ReadAllBytes(from))) continue;
                File.Copy(from, to, true);
            }
            AssetDatabase.Refresh();
            if (!ok) { Debug.LogError($"Story setup {id}: inputs incomplete, pack skipped"); return null; }

            // ---- import settings ----
            var demo = importTexture($"{dir}/Textures/{id}-demo-colored.png", false, 1024);
            var demoSheet = importTexture($"{dir}/Textures/{id}-demo-sheet.png", false, 2048);
            foreach (var f in Directory.GetFiles($"{dir}/Faces", "*.png"))
            {
                string p = f.Replace('\\', '/'); importTexture(p, false, 512);
                var ti = (TextureImporter)AssetImporter.GetAtPath(p); ti.mipmapEnabled = true; ti.alphaIsTransparency = true; ti.SaveAndReimport();
            }
            void Audio(string d, AudioClipLoadType load, float q)
            {
                foreach (var f in Directory.GetFiles(d, "*.wav"))
                {
                    var ai = (AudioImporter)AssetImporter.GetAtPath(f.Replace('\\', '/'));
                    var s = ai.defaultSampleSettings;
                    s.loadType = load; s.compressionFormat = AudioCompressionFormat.Vorbis; s.quality = q;
                    s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate; s.preloadAudioData = true;
                    ai.defaultSampleSettings = s; ai.forceToMono = true; ai.SaveAndReimport();
                }
            }
            Audio($"{res}/voice/zh", AudioClipLoadType.CompressedInMemory, 0.7f);
            Audio($"{res}/voice/en", AudioClipLoadType.CompressedInMemory, 0.7f);
            Audio($"{res}/sfx", AudioClipLoadType.DecompressOnLoad, 0.6f);
            Audio($"{res}/music", AudioClipLoadType.CompressedInMemory, 0.55f);
            foreach (var c in pack.cast) AssetDatabase.ImportAsset($"{dir}/Models/{c.id}.glb", ImportAssetOptions.ForceUpdate);
            if (!string.IsNullOrEmpty(pack.set)) AssetDatabase.ImportAsset($"{dir}/Models/{pack.set}.glb", ImportAssetOptions.ForceUpdate);

            // ---- materials ----
            var sh = Shader.Find("DoodLive/DGPaperLit");
            Material Mat(string name, bool decal)
            {
                string path = $"{dir}/Materials/{name}.mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (!m) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
                m.shader = sh;
                m.SetTexture("_BaseMap", demo);
                m.SetColor("_BaseColor", new Color(0.97f, 0.95f, 0.90f));
                m.SetFloat("_BaseAmt", 0.9f); m.SetFloat("_Smoothness", 0.3f); m.SetFloat("_Metallic", 0); m.SetFloat("_Rim", 0.22f);
                m.SetFloat("_Cull", (float)UnityEngine.Rendering.CullMode.Back); m.SetFloat("_BackTint", 1);
                m.SetFloat("_DecalAmt", decal ? 1 : 0); if (!decal) m.SetTexture("_DecalMap", null);
                m.SetVector("_AmbTint", new Vector4(1.06f, 0.98f, 0.90f, 1));
                EditorUtility.SetDirty(m);
                return m;
            }
            var castMats = pack.cast.Select(c => Mat($"{id}_{c.id}", true)).ToArray();
            Material setMat = null;
            if (!string.IsNullOrEmpty(pack.set))
            {
                setMat = Mat($"{id}_{pack.set}", false);
                if (ColorUtility.TryParseHtmlString(pack.setUnpainted, out var un)) setMat.SetColor("_BaseColor", un);
                setMat.SetFloat("_BaseAmt", 1); setMat.SetFloat("_Rim", 0.08f); setMat.SetFloat("_Smoothness", 0.15f);
            }

            // ---- stage prefab ----
            var clipsJson = File.ReadAllText($"{dir}/Data/clips.json");
            var info = JsonUtility.FromJson<DGClips>(clipsJson);
            var stage = new GameObject("Story_" + id);
            var director = stage.AddComponent<StoryDirector>();
            director.storyId = id; director.titleZh = pack.titleZh; director.titleEn = pack.titleEn; director.demoTexture = demo;
            var shake = new GameObject("Shake").transform; shake.SetParent(stage.transform, false); director.shake = shake;
            var page = new GameObject("DemoPage"); page.transform.SetParent(stage.transform, false);
            page.AddComponent<MeshFilter>();
            var pr = page.AddComponent<MeshRenderer>();
            var pm = Mat($"{id}_demo_page", false);
            pm.SetTexture("_BaseMap", demoSheet); pm.SetColor("_BaseColor", Color.white); pm.SetFloat("_BaseAmt", 0); pm.SetFloat("_Rim", 0);
            pr.sharedMaterial = pm; pr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            director.demoPage = pr;
            var actors = new List<DGActor>(); var sheetX = new List<float>();
            for (int i = 0; i < pack.cast.Length; i++)
            {
                var a = MakeActor(id, pack.cast[i], shake, castMats[i], info);
                if (a) { actors.Add(a); sheetX.Add(pack.cast[i].sheetX); }
            }
            director.actors = actors.ToArray(); director.sheetX = sheetX.ToArray();
            if (setMat) MakeSet(director, $"{dir}/Models/{pack.set}.glb", shake, setMat);
            director.pageMaterials = castMats.Concat(setMat ? new[] { setMat } : new Material[0]).ToArray();
            string prefabPath = $"{dir}/{id}.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(stage, prefabPath);
            Object.DestroyImmediate(stage);
            Debug.Log($"Story setup {id}: prefab {prefabPath}, cast {actors.Count}, set {(setMat ? pack.set : "-")}");
            var r = new Result { entry = e, prefab = prefab };
            r.trackingSheets.Add($"{dir}/Tracking/{id}-A4.png"); r.trackingSheets.Add($"{dir}/Tracking/{id}-A4-demo.png");
            return r;
        }

        static void MakeSet(StoryDirector director, string glb, Transform parent, Material mat)
        {
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(glb);
            if (!model) { Debug.LogError($"Story setup: {glb} did not import"); return; }
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.transform.SetParent(parent, false);
            inst.transform.localPosition = Vector3.zero; inst.transform.localRotation = Quaternion.identity; inst.transform.localScale = Vector3.one;
            foreach (var an in inst.GetComponentsInChildren<Animator>(true)) Object.DestroyImmediate(an);
            director.setAnimator = inst.AddComponent<Animator>(); director.setAnimator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            director.set = inst.transform;
            int n = 0;
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var ms = r.sharedMaterials; for (int i = 0; i < ms.Length; i++) ms[i] = mat; r.sharedMaterials = ms;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On; r.receiveShadows = true;
                if (r is SkinnedMeshRenderer smr) smr.updateWhenOffscreen = true; n++;
            }
            director.setClips = AssetDatabase.LoadAllAssetsAtPath(glb).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__preview")).OrderBy(c => c.name).ToArray();
            Debug.Log($"Story setup: set {inst.name} renderers {n}, clips [{string.Join(" ", director.setClips.Select(c => c.name))}]");
        }

        static DGActor MakeActor(string sid, CastInfo c, Transform parent, Material mat, DGClips info)
        {
            string glb = $"{Dir(sid)}/Models/{c.id}.glb";
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(glb);
            if (!model) { Debug.LogError($"Story setup: {glb} did not import"); return null; }
            var go = new GameObject(char.ToUpper(c.id[0]) + c.id.Substring(1)); go.transform.SetParent(parent, false);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.name = "model"; inst.transform.SetParent(go.transform, false);
            var actor = go.AddComponent<DGActor>();
            actor.id = c.id; actor.height = c.height; actor.material = mat;
            actor.animator = inst.GetComponent<Animator>() ?? inst.AddComponent<Animator>();
            actor.animator.runtimeAnimatorController = null; actor.animator.applyRootMotion = false;
            actor.animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            var all = AssetDatabase.LoadAllAssetsAtPath(glb).OfType<AnimationClip>().Where(x => x.name.StartsWith(c.id + "_")).OrderBy(x => x.name).ToArray();
            actor.clips = all;
            actor.loops = all.Select(x => info.clips.FirstOrDefault(k => k.action == x.name)?.loop ?? false).ToArray();
            actor.speeds = all.Select(x => info.clips.FirstOrDefault(k => k.action == x.name)?.naturalSpeed ?? 0f).ToArray();
            Debug.Log($"Story setup {sid}: {c.id} clips [{all.Length}] {string.Join(" ", all.Select(x => x.name.Substring(c.id.Length + 1)))}");
            Texture2D Face(string expr) => string.IsNullOrEmpty(expr) ? null : AssetDatabase.LoadAssetAtPath<Texture2D>($"{Dir(sid)}/Faces/{c.id}_{expr}.png");
            actor.defaultFace = Face(c.defaultFace);
            actor.faces = all.Select(x =>
            {
                string clip = x.name.Substring(c.id.Length + 1);
                var cf = c.clipFaces?.FirstOrDefault(k => k.clip == clip);
                return Face(cf?.face) ?? actor.defaultFace;
            }).ToArray();
            if (!actor.defaultFace) Debug.LogError($"Story setup {sid}: no default face decal for {c.id} ({c.defaultFace})");
            if (actor.defaultFace) mat.SetTexture("_DecalMap", actor.defaultFace);
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var ms = r.sharedMaterials; for (int i = 0; i < ms.Length; i++) ms[i] = mat; r.sharedMaterials = ms;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
                if (r is SkinnedMeshRenderer smr) smr.updateWhenOffscreen = true;
            }
            foreach (var b in new[] { "root", "hips", "head", "jaw", "handR" })
                if (!inst.GetComponentsInChildren<Transform>(true).Any(t => t.name == b)) Debug.LogError($"Story setup {sid}: {c.id} has no bone {b}");
            return actor;
        }
    }
}
