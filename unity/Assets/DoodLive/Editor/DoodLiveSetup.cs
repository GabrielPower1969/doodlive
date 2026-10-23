// One-shot project generator + Android build. Everything in the project that is not code is made here, so the
// project can be rebuilt from the repo: menu DoodLive > Setup Project, or batch mode in TWO runs (scripts/build-apk.sh):
//   Unity -batchmode -quit -projectPath unity -buildTarget Android -executeMethod DoodLive.EditorTools.DoodLiveSetup.Setup
//   Unity -batchmode -quit -projectPath unity -buildTarget Android -executeMethod DoodLive.EditorTools.DoodLiveSetup.Build
// Setup changes the input handler / scripting defines; building in the same run fails with "script class layout is
// incompatible between the editor and the player" (docs/LESSONS.md L22). SetupAndBuild is for the interactive editor only.
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEditor.XR.ARCore;
using UnityEditor.XR.ARSubsystems;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
using UnityEngine.XR.Management;

namespace DoodLive.EditorTools
{
    public static class DoodLiveSetup
    {
        const string Root = "Assets/DoodLive";
        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
        public const string ApkPath = "Builds/DoodLive.apk";

        [MenuItem("DoodLive/Setup Project")]
        public static void Setup()
        {
            foreach (var d in new[] { "Resources", "Tracking", "Textures", "Materials", "Angel", "Settings", "Scenes" })
                Directory.CreateDirectory(Path.Combine(Root, d));
            CopyInputs();
            var sheets = Sheets.Select(n => ImportTexture($"{Root}/Tracking/{n}.png", readable: true, maxSize: 2048)).ToArray();
            var demo = ImportTexture($"{Root}/Textures/demo-colored.png", readable: false, maxSize: 1024);
            foreach (var ui in Directory.GetFiles($"{Root}/Resources/UI", "*.png"))   // Paper & Crayon icons (tools/make_ui_icons.py): crisp, uncompressed
                ImportTexture(ui.Replace('\\', '/'), readable: false, maxSize: 1024);
            var library = MakeReferenceLibrary(sheets);
            SetupRenderPipeline();
            var mats = MakeMaterials(demo);
            var prefab = MakeAngelPrefabFromGlb(mats) ?? MakeAngelPrefab(mats);   // Blender model (assets/angel) first, code-built fallback
            SetupXR();
            SetupPlayer();
            MakeScene(library, prefab, mats, demo);
            AssetDatabase.SaveAssets();
            Debug.Log("DoodLive setup done");
        }

        [MenuItem("DoodLive/Build Android APK")]
        public static void Build()
        {
            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
                EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            EditorUserBuildSettings.buildAppBundle = false;
            Directory.CreateDirectory("Builds");
            // Build fingerprint (scripts/build-apk.sh exports DOODLIVE_FINGERPRINT = <sha>[-dirty].<UTC>): versionName,
            // a Resources text asset (shown in the HUD, logged at start) and a monotonically increasing versionCode.
            string fp = System.Environment.GetEnvironmentVariable("DOODLIVE_FINGERPRINT");
            if (string.IsNullOrEmpty(fp)) fp = "local." + System.DateTime.UtcNow.ToString("yyyyMMdd-HHmm");
            PlayerSettings.bundleVersion = fp;
            PlayerSettings.Android.bundleVersionCode = (int)(System.DateTime.UtcNow - new System.DateTime(2026, 1, 1)).TotalMinutes;
            Directory.CreateDirectory($"{Root}/Resources");
            File.WriteAllText($"{Root}/Resources/build_fingerprint.txt", fp);
            AssetDatabase.ImportAsset($"{Root}/Resources/build_fingerprint.txt", ImportAssetOptions.ForceUpdate);
            Debug.Log($"DoodLive build fingerprint: {fp}");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { $"{Root}/Scenes/DoodLive.unity" },
                locationPathName = ApkPath,
                target = BuildTarget.Android,
                options = BuildOptions.None,
            });
            Debug.Log($"DoodLive build: {report.summary.result}, {report.summary.totalSize / (1024 * 1024)} MB, {report.summary.totalErrors} errors -> {ApkPath}");
            if (Application.isBatchMode && report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded) EditorApplication.Exit(1);
        }

        public static void SetupAndBuild() { Setup(); Build(); }

        // ---------------- inputs from the web prototype (single source of truth) ----------------
        static void CopyInputs()
        {
            Copy(Path.Combine(RepoRoot, "web/assets/template.json"), $"{Root}/Resources/template.json");
            Copy(Path.Combine(RepoRoot, "print/doodlive-angel-A4.png"), $"{Root}/Tracking/doodlive-angel-A4.png");
            foreach (var n in Sheets.Skip(1)) Copy(Path.Combine(RepoRoot, $"print/previews/{n}.png"), $"{Root}/Tracking/{n}.png");
            Copy(Path.Combine(RepoRoot, "web/assets/demo-colored.png"), $"{Root}/Textures/demo-colored.png");
            AssetDatabase.Refresh();
        }

        static void Copy(string src, string dst)
        {
            if (File.Exists(dst) && File.ReadAllBytes(dst).SequenceEqual(File.ReadAllBytes(src))) return;
            File.Copy(src, dst, true);
        }

        static Texture2D ImportTexture(string path, bool readable, int maxSize)
        {
            var ti = (TextureImporter)AssetImporter.GetAtPath(path);
            ti.textureType = TextureImporterType.Default;
            ti.isReadable = readable;
            ti.mipmapEnabled = false;
            ti.npotScale = TextureImporterNPOTScale.None;
            ti.textureCompression = TextureImporterCompression.Uncompressed;
            ti.wrapMode = TextureWrapMode.Clamp;
            ti.maxTextureSize = maxSize;
            ti.sRGBTexture = true;
            ti.alphaIsTransparency = true;
            ti.SaveAndReimport();
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        // Every printable sheet must be in the tracking library: ARCore only finds images it was given. The themed
        // sheets share the plain sheet's markers and art rectangle, so capture/warp is identical (docs/LESSONS.md L23).
        // p1 = blank colouring page, p2 = coloured example (people also scan it straight off a screen).
        static readonly string[] Sheets = { "doodlive-angel-A4",
            "fiery-p1", "fiery-p2", "wrath-p1", "wrath-p2", "holy-p1", "holy-p2" };

        static XRReferenceImageLibrary MakeReferenceLibrary(Texture2D[] sheets)
        {
            string path = $"{Root}/Tracking/ReferenceImages.asset";
            var lib = AssetDatabase.LoadAssetAtPath<XRReferenceImageLibrary>(path);
            if (!lib) { lib = ScriptableObject.CreateInstance<XRReferenceImageLibrary>(); AssetDatabase.CreateAsset(lib, path); }
            while (lib.count > 0) lib.RemoveAt(0);
            for (int i = 0; i < sheets.Length; i++)
            {
                lib.Add();
                lib.SetTexture(i, sheets[i], false);
                lib.SetName(i, sheets[i].name);
                // Do NOT pin the size to A4: sheets are also scanned off laptop / iPad screens. A wrong physical size puts
                // the image (and the angel) at the wrong depth, so she slides against the drawing as you move (LESSONS L25).
                // ARCore estimates the real size instead; the controller re-fits to it every frame.
                lib.SetSpecifySize(i, false);
                lib.SetSize(i, new Vector2(0.210f, 0.297f)); // hint only (A4 portrait, metres)
            }
            EditorUtility.SetDirty(lib);
            return lib;
        }

        // ---------------- URP ----------------
        static void SetupRenderPipeline()
        {
            string rPath = $"{Root}/Settings/URP_Renderer.asset", aPath = $"{Root}/Settings/URP.asset";
            var data = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(rPath);
            if (!data)
            {
                data = ScriptableObject.CreateInstance<UniversalRendererData>();
                AssetDatabase.CreateAsset(data, rPath);
                ResourceReloader.TryReloadAllNullIn(data, UniversalRenderPipelineAsset.packagePath);
            }
            if (!data.rendererFeatures.OfType<ARBackgroundRendererFeature>().Any())
            {
                var f = ScriptableObject.CreateInstance<ARBackgroundRendererFeature>();
                f.name = "ARBackgroundRendererFeature";
                AssetDatabase.AddObjectToAsset(f, data);
                data.rendererFeatures.Add(f);
                var so = new SerializedObject(data);
                var map = so.FindProperty("m_RendererFeatureMap");
                AssetDatabase.TryGetGUIDAndLocalFileIdentifier(f, out _, out long id);
                map.arraySize++;
                map.GetArrayElementAtIndex(map.arraySize - 1).longValue = id;
                so.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(data);
            }
            var asset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(aPath);
            if (!asset)
            {
                asset = UniversalRenderPipelineAsset.Create(data);
                AssetDatabase.CreateAsset(asset, aPath);
            }
            asset.supportsHDR = false;          // AR camera feed is LDR; saves bandwidth on phones
            asset.msaaSampleCount = 2;
            asset.shadowDistance = 3;
            EditorUtility.SetDirty(asset);
            GraphicsSettings.defaultRenderPipeline = asset;
            for (int i = 0; i < QualitySettings.names.Length; i++)
            {
                QualitySettings.SetQualityLevel(i, false);
                QualitySettings.renderPipeline = asset;
            }
        }

        // ---------------- materials ----------------
        static Dictionary<string, Material> MakeMaterials(Texture2D demo)
        {
            var paper = Shader.Find("DoodLive/PaperLit");
            var M = new Dictionary<string, Material>();
            Material Mat(string name, Shader sh)
            {
                string path = $"{Root}/Materials/{name}.mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (!m) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
                m.shader = sh;
                return M[name] = m;
            }
            void Paper(string name, string hex, float baseAmt = 0.9f, float rough = 0.75f, float metal = 0, float rim = 0.25f, bool twoSided = false, float backTint = 1)
            {
                var m = Mat(name, paper);
                ColorUtility.TryParseHtmlString(hex, out var c);
                m.SetTexture("_BaseMap", demo);
                m.SetColor("_BaseColor", c);
                m.SetFloat("_BaseAmt", baseAmt);
                m.SetFloat("_Smoothness", 1 - rough);
                m.SetFloat("_Metallic", metal);
                m.SetFloat("_Rim", rim);
                m.SetFloat("_Cull", (float)(twoSided ? CullMode.Off : CullMode.Back));
                m.SetFloat("_BackTint", backTint);
            }
            // same defaults as makeMaterial() in angel.js
            Paper("robe", "#f4f4f8", rim: 0.35f);
            Paper("skin", "#f3cdb4", baseAmt: 0.95f, rough: 0.6f, rim: 0.15f);
            Paper("hair", "#8a5a32", rough: 0.9f, rim: 0.2f);
            Paper("wing", "#f7f5ef", rim: 0.4f, twoSided: true, backTint: 0.85f);
            Paper("gold", "#d9a43a", metal: 0.85f, rough: 0.3f, rim: 0.3f);
            Paper("cloud", "#ffffff", baseAmt: 1, rough: 1, rim: 0.3f);
            M["cloud"].SetTexture("_BaseMap", Texture2D.whiteTexture);
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            void Plain(string name, string hex, float smooth = 0.4f)
            {
                var m = Mat(name, lit); ColorUtility.TryParseHtmlString(hex, out var c);
                m.SetColor("_BaseColor", c); m.SetFloat("_Smoothness", smooth);
            }
            Plain("eyewhite", "#f7f5ee", 0.75f); Plain("iris", "#4d85b8", 0.7f); Plain("pupil", "#08080a", 0.8f);
            Plain("lash", "#2b1a12", 0.3f); Plain("brow", "#7a4d29", 0.2f); Plain("lip", "#d97a78", 0.5f); Plain("sash", "#cfae66", 0.45f);
            var halo = Mat("halo", Shader.Find("Universal Render Pipeline/Unlit"));
            ColorUtility.TryParseHtmlString("#ffe9a0", out var hc);
            halo.SetColor("_BaseColor", hc);
            foreach (var m in M.Values) EditorUtility.SetDirty(m);
            return M;
        }

        // ---------------- angel prefab + animation ----------------
        static GameObject MakeAngelPrefab(Dictionary<string, Material> mats)
        {
            string meshPath = $"{Root}/Angel/AngelMeshes.asset", prefabPath = $"{Root}/Angel/Angel.prefab";
            AssetDatabase.DeleteAsset(meshPath);
            var A = AngelBuilder.Build(mats);
            var container = ScriptableObject.CreateInstance<MeshContainer>();
            AssetDatabase.CreateAsset(container, meshPath);
            foreach (var m in A.meshes) AssetDatabase.AddObjectToAsset(m, container);

            A.halo.gameObject.AddComponent<Spin>().axis = Vector3.forward;
            var cs = A.cloud.gameObject.AddComponent<Spin>();
            cs.axis = Vector3.up; cs.radiansPerSecond = 0.1f; cs.bobAmplitude = 0.02f;

            var animator = A.root.AddComponent<Animator>();
            animator.applyRootMotion = false;
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            animator.runtimeAnimatorController = MakeController(A);
            var prefab = PrefabUtility.SaveAsPrefabAsset(A.root, prefabPath);
            Object.DestroyImmediate(A.root);
            return prefab;
        }

        /// <summary>
        /// The Blender-built angel (pipeline/angel_build.py -> assets/angel/angel.glb), imported by glTFast. Its node
        /// hierarchy carries the rig names (hips … wingRtip) as plain Transforms with identity rotation, so the same
        /// AngelPose clips drive it. Materials are remapped by name to the PaperLit set (page-coloured parts) or the
        /// plain Lit face materials. Returns null when the model or the importer is missing (code-built fallback).
        /// </summary>
        static GameObject MakeAngelPrefabFromGlb(Dictionary<string, Material> mats)
        {
            string src = Path.Combine(RepoRoot, "assets/angel/angel.glb"), dst = $"{Root}/Angel/angel.glb";
            if (!File.Exists(src)) { Debug.LogWarning("DoodLive: assets/angel/angel.glb not found, using the code-built angel"); return null; }
            Copy(src, dst); AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(dst);
            if (!model) { Debug.LogWarning("DoodLive: angel.glb did not import (is com.unity.cloud.gltfast installed?)"); return null; }

            var A = new AngelBuilder.Parts { root = new GameObject("Angel"), rig = new GameObject("rig") };
            A.rig.transform.SetParent(A.root.transform, false);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(model);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.name = "model"; inst.transform.SetParent(A.rig.transform, false);
            foreach (var t in inst.GetComponentsInChildren<Transform>(true))
            {
                if (System.Array.IndexOf(AngelBuilder.BoneNames, t.name) >= 0) A.bones[t.name] = t;
                if (t.name == "halo") A.halo = t;
                if (t.name == "cloud") A.cloud = t;
            }
            foreach (var n in AngelBuilder.BoneNames) if (!A.bones.ContainsKey(n)) Debug.LogError($"DoodLive: angel.glb has no node '{n}'");
            var w = A.bones["wristR"].position; Debug.Log($"DoodLive glb rig check: wristR at {w} (expect x>0, y>0), head at {A.bones["head"].position}");

            var byName = new Dictionary<string, string> { ["sash"] = "sash" };
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var ms = r.sharedMaterials;
                for (int i = 0; i < ms.Length; i++)
                {
                    string n = ms[i] ? ms[i].name.Replace(" (Instance)", "") : "robe";
                    if (byName.TryGetValue(n, out var alias)) n = alias;
                    ms[i] = mats.TryGetValue(n, out var m) ? m : mats["robe"];
                }
                r.sharedMaterials = ms;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            }
            A.halo.gameObject.AddComponent<Spin>().axis = Vector3.up;
            var cs = A.cloud.gameObject.AddComponent<Spin>(); cs.axis = Vector3.up; cs.radiansPerSecond = 0.1f; cs.bobAmplitude = 0.02f;
            // 3D titles (pipeline/make_title.py): Chinese over English/pinyin, one per sheet theme; the controller enables
            // the right one. Each instance gets its own Billboard; mirroring / readable side come from the env
            // (DOODLIVE_TITLE_MIRROR=1, DOODLIVE_TITLE_FRONT=-1), decided empirically on device (LESSONS L30).
            // DOODLIVE_TITLE_TEST=1 lays out all four combinations in a grid for one on-device photo.
            var titles = new GameObject("titles"); titles.transform.SetParent(A.root.transform, false);
            titles.transform.localPosition = new Vector3(0, 1.42f, 0); titles.transform.localScale = Vector3.one * 0.6f;
            bool test = System.Environment.GetEnvironmentVariable("DOODLIVE_TITLE_TEST") == "1";
            float mirror = System.Environment.GetEnvironmentVariable("DOODLIVE_TITLE_MIRROR") == "1" ? -1f : 1f;
            int front = System.Environment.GetEnvironmentVariable("DOODLIVE_TITLE_FRONT") == "-1" ? -1 : 1;
            GameObject LoadTitle(string key, string name)
            {
                string tsrc = Path.Combine(RepoRoot, $"assets/titles/{key}.glb"), tdst = $"{Root}/Angel/title_{key}.glb";
                if (!File.Exists(tsrc)) return null;
                Copy(tsrc, tdst); AssetDatabase.ImportAsset(tdst, ImportAssetOptions.ForceUpdate);
                var tm = AssetDatabase.LoadAssetAtPath<GameObject>(tdst); if (!tm) return null;
                var ti = (GameObject)PrefabUtility.InstantiatePrefab(tm); PrefabUtility.UnpackPrefabInstance(ti, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
                ti.name = name; ti.transform.SetParent(titles.transform, false); return ti;
            }
            if (test)
            {   // A: scale+ front+ (top-left)   B: scale- front+ (top-right)   C: scale+ front- (bottom-left)   D: scale- front- (bottom-right)
                var combos = new (string, float, int, Vector3)[] { ("A", 1, 1, new Vector3(-0.7f, 0.45f, 0)), ("B", -1, 1, new Vector3(0.7f, 0.45f, 0)),
                                                                  ("C", 1, -1, new Vector3(-0.7f, -0.45f, 0)), ("D", -1, -1, new Vector3(0.7f, -0.45f, 0)) };
                foreach (var (n, sc, fr, pos) in combos)
                {
                    var ti = LoadTitle("angel", "angel_" + n); if (!ti) continue;
                    var holder = new GameObject("holder_" + n); holder.transform.SetParent(titles.transform, false); holder.transform.localPosition = pos;
                    ti.transform.SetParent(holder.transform, false); ti.transform.localScale = new Vector3(sc, 1, 1);
                    holder.AddComponent<Billboard>().frontSign = fr;
                }
            }
            else
            {
                foreach (var key in new[] { "angel", "fiery", "wrath", "holy" })
                {
                    var ti = LoadTitle(key, key); if (!ti) continue;
                    ti.SetActive(key == "angel"); ti.transform.localScale = new Vector3(mirror, 1, 1);
                    ti.AddComponent<Billboard>().frontSign = front;
                }
            }
            var animator = A.root.AddComponent<Animator>();
            animator.applyRootMotion = false; animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            glbRig = true; animator.runtimeAnimatorController = MakeController(A); glbRig = false;
            string prefabPath = $"{Root}/Angel/Angel.prefab";
            var prefab = PrefabUtility.SaveAsPrefabAsset(A.root, prefabPath);
            Object.DestroyImmediate(A.root);
            Debug.Log("DoodLive: angel prefab built from assets/angel/angel.glb");
            return prefab;
        }

        static AnimatorController MakeController(AngelBuilder.Parts A)
        {
            var enter = BakeClip(A, Phase.Enter, AngelPose.EnterLength, loop: false);
            var idle = BakeClip(A, Phase.Idle, AngelPose.IdleLength, loop: true);
            var blow = BakeClip(A, Phase.Blow, AngelPose.BlowLength, loop: false);

            string path = $"{Root}/Angel/Angel.controller";
            AssetDatabase.DeleteAsset(path);
            var c = AnimatorController.CreateAnimatorControllerAtPath(path);
            c.AddParameter("Blow", AnimatorControllerParameterType.Trigger);
            var sm = c.layers[0].stateMachine;
            var sEnter = sm.AddState("Enter"); sEnter.motion = enter;
            var sIdle = sm.AddState("Idle"); sIdle.motion = idle;
            var sBlow = sm.AddState("Blow"); sBlow.motion = blow;
            sm.defaultState = sEnter;

            var t = sEnter.AddTransition(sIdle);
            t.hasExitTime = true; t.exitTime = 0.95f; t.duration = 0.1f; t.hasFixedDuration = true;
            t = sIdle.AddTransition(sBlow);
            t.hasExitTime = false; t.duration = 0.15f; t.hasFixedDuration = true;
            t.AddCondition(AnimatorConditionMode.If, 0, "Blow");
            t = sBlow.AddTransition(sIdle);
            t.hasExitTime = true; t.exitTime = 0.92f; t.duration = 0.25f; t.hasFixedDuration = true;
            return c;
        }

        // glTFast maps glTF (right-handed, = three.js) to Unity by mirroring X, while AngelBuilder / AngelPose.ToUnity
        // mirror Z. The two differ by a 180° turn about Y, so for the GLB rig every bone rotation is conjugated by that
        // turn: quaternion (x, y, z, w) -> (-x, y, -z, w). Set while the GLB prefab is being baked.
        static bool glbRig;
        static Quaternion ForRig(Quaternion q) => glbRig ? new Quaternion(-q.x, q.y, -q.z, q.w) : q;

        static AnimationClip BakeClip(AngelBuilder.Parts A, Phase phase, float length, bool loop)
        {
            const int fps = 30;
            var clip = new AnimationClip { name = phase.ToString(), frameRate = fps };
            var curves = new Dictionary<(string path, string prop), AnimationCurve>();
            void Key(string path, string prop, float time, float v)
            {
                if (!curves.TryGetValue((path, prop), out var c)) curves[(path, prop)] = c = new AnimationCurve();
                c.AddKey(new Keyframe(time, v));
            }
            var lastQ = new Dictionary<string, Quaternion>();
            void Rot(string path, float time, Quaternion q)
            {
                if (lastQ.TryGetValue(path, out var prev) && Quaternion.Dot(prev, q) < 0) q = new Quaternion(-q.x, -q.y, -q.z, -q.w);
                lastQ[path] = q;
                Key(path, "m_LocalRotation.x", time, q.x); Key(path, "m_LocalRotation.y", time, q.y);
                Key(path, "m_LocalRotation.z", time, q.z); Key(path, "m_LocalRotation.w", time, q.w);
            }
            int frames = Mathf.RoundToInt(length * fps);
            for (int f = 0; f <= frames; f++)
            {
                float t = f / (float)fps;
                var p = AngelPose.Sample(phase, t, t);
                if (phase == Phase.Enter)
                {
                    Key("", "m_LocalScale.x", t, p.rootScale); Key("", "m_LocalScale.y", t, p.rootScale); Key("", "m_LocalScale.z", t, p.rootScale);
                }
                Key("rig", "m_LocalPosition.x", t, 0); Key("rig", "m_LocalPosition.y", t, p.rigY); Key("rig", "m_LocalPosition.z", t, 0);
                Rot("rig", t, Quaternion.AngleAxis(-p.rigSpin * Mathf.Rad2Deg, Vector3.up));
                foreach (var kv in p.euler)
                {
                    var bone = A.bones[kv.Key];
                    string path = AnimationUtility.CalculateTransformPath(bone, A.root.transform);
                    Rot(path, t, ForRig(AngelPose.ToUnity(kv.Value)));
                }
            }
            foreach (var kv in curves) clip.SetCurve(kv.Key.path, typeof(Transform), kv.Key.prop, kv.Value);
            clip.EnsureQuaternionContinuity();
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            settings.loopTime = loop;
            AnimationUtility.SetAnimationClipSettings(clip, settings);
            string path2 = $"{Root}/Angel/{clip.name}.anim";
            AssetDatabase.DeleteAsset(path2);
            AssetDatabase.CreateAsset(clip, path2);
            return clip;
        }

        // ---------------- XR + player ----------------
        static void SetupXR()
        {
            if (!EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget))
            {
                Directory.CreateDirectory("Assets/XR");
                perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                AssetDatabase.CreateAsset(perTarget, "Assets/XR/XRGeneralSettingsPerBuildTarget.asset");
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
            }
            if (!perTarget.HasSettingsForBuildTarget(BuildTargetGroup.Android)) perTarget.CreateDefaultSettingsForBuildTarget(BuildTargetGroup.Android);
            if (!perTarget.HasManagerSettingsForBuildTarget(BuildTargetGroup.Android)) perTarget.CreateDefaultManagerSettingsForBuildTarget(BuildTargetGroup.Android);
            var general = perTarget.SettingsForBuildTarget(BuildTargetGroup.Android);
            general.InitManagerOnStart = true;
            XRPackageMetadataStore.AssignLoader(general.Manager, "UnityEngine.XR.ARCore.ARCoreLoader", BuildTargetGroup.Android);
            EditorUtility.SetDirty(perTarget);

            var arcore = ARCoreSettings.GetOrCreateSettings();
            arcore.requirement = ARCoreSettings.Requirement.Required;  // AR-only app: Play Store lists it for ARCore phones
            arcore.depth = ARCoreSettings.Requirement.Optional;
            EditorUtility.SetDirty(arcore);
            ARCoreSettings.currentSettings = arcore;
        }

        static void SetupPlayer()
        {
            PlayerSettings.companyName = "One More Thing";
            PlayerSettings.productName = "DoodLive";
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "today.onemorething.doodlive");
            PlayerSettings.bundleVersion = "0.1.0";
            PlayerSettings.Android.bundleVersionCode = 1;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel24;
            PlayerSettings.Android.targetSdkVersion = (AndroidSdkVersions)34;
            PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.OpenGLES3 });
            PlayerSettings.colorSpace = ColorSpace.Linear;
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.AutoRotation;   // phones + tablets (Akita is used landscape)
            PlayerSettings.allowedAutorotateToPortrait = true;
            PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
            PlayerSettings.allowedAutorotateToLandscapeLeft = true;
            PlayerSettings.allowedAutorotateToLandscapeRight = true;
            PlayerSettings.Android.startInFullscreen = true;

            // Input: legacy (touches / IMGUI) and the Input System (TrackedPoseDriver) together
            var ps = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset").FirstOrDefault();
            if (ps)
            {
                var so = new SerializedObject(ps);
                var p = so.FindProperty("activeInputHandler");
                if (p != null && p.intValue != 2) { p.intValue = 2; so.ApplyModifiedPropertiesWithoutUndo(); }
            }
        }

        // ---------------- scene ----------------
        static void MakeScene(XRReferenceImageLibrary library, GameObject angelPrefab, Dictionary<string, Material> mats, Texture2D demo)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var sessionGo = new GameObject("AR Session");
            var session = sessionGo.AddComponent<ARSession>();
            sessionGo.AddComponent<ARInputManager>();

            var originGo = new GameObject("XR Origin");
            var origin = originGo.AddComponent<XROrigin>();
            var offset = new GameObject("Camera Offset");
            offset.transform.SetParent(originGo.transform, false);
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            camGo.transform.SetParent(offset.transform, false);
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Color.black;
            cam.nearClipPlane = 0.01f; cam.farClipPlane = 30;
            camGo.AddComponent<AudioListener>();
            var camMgr = camGo.AddComponent<ARCameraManager>();
            camMgr.requestedFacingDirection = CameraFacingDirection.World;
            camMgr.requestedLightEstimation = LightEstimation.None;
            var bg = camGo.AddComponent<ARCameraBackground>();
            var tpd = camGo.AddComponent<UnityEngine.InputSystem.XR.TrackedPoseDriver>();
            var pos = new InputAction("Position", binding: "<HandheldARInputDevice>/devicePosition");
            var rot = new InputAction("Rotation", binding: "<HandheldARInputDevice>/deviceRotation");
            tpd.positionInput = new InputActionProperty(pos);
            tpd.rotationInput = new InputActionProperty(rot);
            origin.Camera = cam;
            origin.CameraFloorOffsetObject = offset;
            origin.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.NotSpecified;

            var images = originGo.AddComponent<ARTrackedImageManager>();
            images.referenceLibrary = library;
            images.requestedMaxNumberOfMovingImages = 1;
            originGo.AddComponent<ARAnchorManager>();   // fallback anchors (ARColoringController.AnchorHere)

            var light = new GameObject("Directional Light").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.1f;
            light.shadows = LightShadows.Soft;
            light.transform.rotation = Quaternion.Euler(50, -30, 0);
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.85f, 0.88f, 1f);
            RenderSettings.ambientEquatorColor = new Color(0.7f, 0.7f, 0.75f);
            RenderSettings.ambientGroundColor = new Color(0.45f, 0.42f, 0.4f);

            var angel = (GameObject)PrefabUtility.InstantiatePrefab(angelPrefab);

            var app = new GameObject("DoodLive");
            var ctl = app.AddComponent<ARColoringController>();
            ctl.session = session; ctl.trackedImages = images; ctl.cameraManager = camMgr; ctl.cameraBackground = bg; ctl.arCamera = cam;
            ctl.angel = angel.GetComponent<Animator>();
            ctl.pageMaterials = new[] { mats["robe"], mats["skin"], mats["hair"], mats["wing"], mats["gold"] };   // cloud stays white (not page-coloured)
            ctl.demoTexture = demo;
            ctl.sfx = app.AddComponent<AudioSource>();
            ctl.voice = app.AddComponent<AudioSource>();
            ctl.music = app.AddComponent<AudioSource>();
            ctl.sfx.playOnAwake = ctl.voice.playOnAwake = ctl.music.playOnAwake = false;
            ctl.music.loop = true; ctl.music.volume = 0.22f; ctl.voice.volume = 1f; ctl.sfx.volume = 0.8f;
            AudioClip Clip(string n) => AssetDatabase.LoadAssetAtPath<AudioClip>($"{Root}/Audio/{n}.wav");
            ctl.fanfare = Clip("fanfare"); ctl.chime = Clip("chime"); ctl.hello = Clip("voice_hello");
            ctl.music.clip = Clip("theme"); ctl.swell = Clip("swell");
            ctl.lines = new[] { Clip("voice_0"), Clip("voice_1"), Clip("voice_2"), Clip("voice_3") };
            ctl.greets = new[] { Clip("fly"), Clip("wow"), Clip("laugh") };
            ctl.helloEn = Clip("en_voice_hello");
            ctl.linesEn = new[] { Clip("en_voice_0"), Clip("en_voice_1"), Clip("en_voice_2"), Clip("en_voice_3") };
            ctl.greetsEn = new[] { Clip("en_greet0"), Clip("en_greet1"), Clip("en_greet2") };

            string path = $"{Root}/Scenes/DoodLive.unity";
            EditorSceneManager.SaveScene(scene, path);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(path, true) };
        }
    }
}
