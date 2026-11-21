// DGDirector plays assets/david-goliath/timeline.json (CONTRACT §6) on the two DGActors: acting (clips with
// cross-fades and moves across the page), lines (voice in the current language + subtitle data for the UI), fx
// (DGFx.Play), sfx and music (cue cross-fades). It owns performance time: pause freezes animation, audio and effects
// at the same instant, replay restarts from 0. Drawing (subtitles, pause card, replay chip) is done by
// ARColoringController.UI in the Paper & Crayon style; this class only exposes what to draw.
//
// Space: this transform is DGFx.Stage, local unit = 1 art width, page at local y = 0, local +Z = toward the viewer
// (page bottom). The timeline's design axes (glTF: x = viewer's right) map to Unity local (-x, y, z), the same
// handedness flip glTFast applies to the models (docs/LESSONS.md L26), so positions and the models agree.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace DoodLive.DavidGoliath
{
    public class DGDirector : MonoBehaviour, IStoryPlayer
    {
        public string StoryId => "david-goliath";
        public float MusicGain { get => MusicLevel; set => MusicLevel = value; }
        public Camera Cinematic { get => cinematic; set => cinematic = value; }
        public DGActor david, goliath;
        [Tooltip("Identity pivot above both actors; DGFx shakes it (never the AR holder)")]
        public Transform shake;
        [Tooltip("Flat printed page under the actors, shown only in the demo (the real sheet is there in AR)")]
        public MeshRenderer demoPage;
        [Tooltip("Sand ground over the whole page (CONTRACT §12.4, DoodLive/DGGround), under the shake pivot; AR and demo")]
        public MeshRenderer ground;
        [Tooltip("design.json characters.<id>.sheetX: where each figure is drawn, so they stand up from their drawing")]
        public float davidSheetX = -0.350f, goliathSheetX = 0.130f;   // CONTRACT §11.4 (DGSetup copies design.json)

        [Header("Desert set (CONTRACT §11.9, assets/david-goliath/model/desert.glb)")]
        [Tooltip("Instance root of desert.glb (node 'desert'), child of the shake pivot like the actors")]
        public Transform desert;
        [Tooltip("Banner wave clips of desert.glb (bannerIsraelWave, bannerPhilWave), played on the desert root's Animator")]
        public AnimationClip[] desertClips;
        [Tooltip("Animator on the desert root (no controller): a player can only play non-legacy clips through an Animator")]
        public Animator desertAnimator;
        [Tooltip("desert/fiveStones/stone1..5: hidden one by one while David picks them up")]
        public Renderer[] desertStones;
        [Tooltip("Seconds into david_kneel_pick at which each desert stone is hidden (clips.json desertEvents)")]
        public float[] desertStoneHideSec;
        [Tooltip("Seconds into david_kneel_pick at which David's own stone appears in his hand (clips.json marker pick5)")]
        public float stoneShowSec = 2.733f;

        public const string ResDir = "DG/";

        // ---------------- state the UI reads ----------------
        public bool Running { get; private set; }
        public bool Finished => Running && now >= tl.duration;
        public bool Paused { get; set; }               // child's tap
        public bool Hold { get; set; }                 // system: sheet lost / app in background
        public float Now => now;
        public float Duration => tl != null ? tl.duration : 0;
        public DGTimeline Timeline => tl;
        public DGLine Line { get; private set; }       // line being spoken (subtitle), null when none
        public float LineAge => Line != null ? now - Line.t : 0;
        public DGShot Shot { get; private set; }
        public float ShotAge => Shot != null ? now - Shot.t0 : 0;
        /// <summary>Music level from the grown-ups slider (1 = as mixed).</summary>
        public float MusicLevel = 1f;
        /// <summary>Cinematic camera for the demo without AR: follows the shot list's camera hints. Null in AR.</summary>
        public Camera cinematic;

        DGTimeline tl;
        DGCues cues;
        readonly Dictionary<string, DGSfxMixEntry> mix = new Dictionary<string, DGSfxMixEntry>();
        readonly Dictionary<string, AudioClip> clipCache = new Dictionary<string, AudioClip>();
        float now, lineEnd;
        int iAct, iLine, iFx, iSfx, iMusic;
        bool frozen, stoneOn, stoneThrown;
        AudioSource voice, sfx, sfxLoop, musicA, musicB; string loopId; float voiceDuck = 1;
        AudioSource musicCur, musicOld; float musicOldFrom; float musicFadeT;
        float camFixedFor = -1; Vector3 camFixedTarget;
        float desertT;                                   // banner wave time (runs while the play runs, also after the end)
        PlayableGraph desertGraph;                       // one layer per banner clip, so each clip keeps only its own banner
        AnimationClipPlayable[] desertPlayables;

        // =====================================================================================================
        void Awake() => Init();

        void Init()
        {
            if (voice) return;
            voice = NewSource("voice"); sfx = NewSource("sfx"); sfxLoop = NewSource("sfxLoop"); sfxLoop.loop = true;
            musicA = NewSource("musicA"); musicB = NewSource("musicB");
            BuildDemoPage();
            BuildGround();
            ShowDemoPage(false);
        }

        AudioSource NewSource(string n)
        {
            var go = new GameObject("audio_" + n); go.transform.SetParent(transform, false);
            var s = go.AddComponent<AudioSource>(); s.playOnAwake = false; s.spatialBlend = 0; return s;
        }

        bool LoadData()
        {
            if (tl != null) return true;
            var j = Resources.Load<TextAsset>(ResDir + "timeline");
            if (!j) { Debug.LogError("DG: Resources/DG/timeline.json missing (run DoodLive > Setup Project)"); return false; }
            tl = DGTimeline.Load(j.text);
            var m = Resources.Load<TextAsset>(ResDir + "sfx_mix");
            if (m) foreach (var e in JsonUtility.FromJson<DGSfxMix>(m.text).sfx) mix[e.id] = e;
            var c = Resources.Load<TextAsset>(ResDir + "music_cues");
            cues = c ? JsonUtility.FromJson<DGCues>(c.text) : new DGCues();
            Debug.Log($"DG timeline v{tl.version}: {tl.duration} s, {tl.acting.Length} acting, {tl.lines.Length} lines, {tl.fx.Length} fx, {tl.sfx.Length} sfx, {tl.music.Length} music");
            return true;
        }

        AudioClip Clip(string path)
        {
            if (!clipCache.TryGetValue(path, out var c)) { c = Resources.Load<AudioClip>(ResDir + path); clipCache[path] = c; if (!c) Debug.LogWarning("DG: missing audio " + path); }
            return c;
        }

        // ---------------- control ----------------
        /// <summary>Start (or restart) the play from 0.</summary>
        public void Begin()
        {
            if (!LoadData()) return;
            Init();
            StopAudio(); DGFx.StopAll();
            DGFx.Stage = transform; DGFx.ShakeTarget = shake; if (fxEnabled) DGFx.Prewarm();
            now = 0; lineEnd = 0; iAct = iLine = iFx = iSfx = iMusic = 0; Line = null; Shot = null;
            Paused = false; Hold = false; frozen = false; stoneOn = false; stoneThrown = false; camFixedFor = -1;
            ResetActor(david, davidSheetX); ResetActor(goliath, goliathSheetX);
            desertT = 0;
            if (desertStones != null) foreach (var r in desertStones) if (r) r.enabled = true;
            Running = true;
            gameObject.SetActive(true);
            Step(0);
        }

        void ResetActor(DGActor a, float x)
        {
            a.Init();
            a.pos = new Vector2(x, 0); a.yaw = 0; a.face = "viewer"; a.cur = a.prev = -1; a.moving = false; a.curRate = 1;
            a.cur = Mathf.Max(0, a.Clip("idle")); a.curT0 = 0; a.SetFace(a.cur);
            Place(a);
        }

        public void Replay() => Begin();

        // ---------------- start at a shot (library "keep reading"): a silent fast-forward ----------------
        bool seeking; readonly List<DGFxCue> seekFx = new List<DGFxCue>(); DGMusicCue seekMusic; DGSfxCue seekLoop;

        public void BeginAt(int shot)
        {
            seeking = true; seekFx.Clear(); seekMusic = null; seekLoop = null;
            Begin();
            if (!Running || tl == null || tl.shots == null || shot <= 0 || shot >= tl.shots.Length) { EndSeek(0); return; }
            float t = tl.shots[shot].t0;
            while (now < t - 1e-3f) Step(Mathf.Min(0.1f, t - now));
            EndSeek(t);
        }

        void EndSeek(float t)
        {
            seeking = false;
            foreach (var f in seekFx)
            {
                float end = f.t + (f.dur > 0 ? f.dur : 1f);
                if (end > t + 0.05f) { var g = f; if (f.dur > 0) { g = new DGFxCue { t = f.t, dur = end - t, id = f.id, at = f.at, to = f.to }; } Fx(g); }
            }
            seekFx.Clear();
            if (seekLoop != null && (seekMusic == null || seekLoop.t >= seekMusic.t)) Sfx(seekLoop);
            seekLoop = null;
            if (seekMusic != null)
            {
                var m = seekMusic; seekMusic = null; Music(m);
                if (musicCur && musicCur.clip) musicCur.time = Mathf.Clamp(t - m.t, 0, Mathf.Max(0, musicCur.clip.length - 0.05f));
            }
        }

        /// <summary>Stop everything (leaving the sheet, new scan). The stage is hidden by the caller.</summary>
        public void Stop()
        {
            Running = false; Line = null; Shot = null;
            StopAudio(); DGFx.StopAll(); DGFx.Paused = false;
            if (cinematic) cinematic = null;
        }

        /// <summary>Editor preview (DGPreview): set up without Awake and step time by hand; effects are skipped there.</summary>
        public void EditorInit() { Init(); fxEnabled = false; }
        public void EditorStep(float dt) { if (Running) Step(dt); }
        [System.NonSerialized] public bool fxEnabled = true;

        public void TogglePause() { if (Running && !Finished) Paused = !Paused; }

        void StopAudio()
        {
            foreach (var s in new[] { voice, sfx, sfxLoop, musicA, musicB }) if (s) s.Stop();
            musicCur = musicOld = null; loopId = null;
        }

        void SetFrozen(bool f)
        {
            if (f == frozen) return;
            frozen = f; DGFx.Paused = f;
            foreach (var s in new[] { voice, sfx, sfxLoop, musicA, musicB }) { if (!s) continue; if (f) s.Pause(); else s.UnPause(); }
        }

        // =====================================================================================================
        void Update()
        {
            if (!Running) return;
            SetFrozen(Paused || Hold);
            float dt = frozen ? 0 : Time.deltaTime;
            Step(dt);
        }

        void Step(float dt)
        {
            if (!Finished) now = Mathf.Min(tl.duration, now + dt);
            Events();
            Shot = tl.ShotAt(now);
            if (Line != null && now > lineEnd) Line = null;
            foreach (var a in new[] { david, goliath }) { Move(a, dt); Place(a); a.Evaluate(now); }
            Desert(dt);
            if (david.stone) david.stone.enabled = stoneOn;
            Mix(dt);
            if (cinematic) DriveCamera(cinematic);
        }

        void Events()
        {
            while (iAct < tl.acting.Length && tl.acting[iAct].t <= now + 1e-4f) Act(tl.acting[iAct], iAct++);
            while (iLine < tl.lines.Length && tl.lines[iLine].t <= now + 1e-4f) Say(tl.lines[iLine++]);
            while (iFx < tl.fx.Length && tl.fx[iFx].t <= now + 1e-4f) Fx(tl.fx[iFx++]);
            while (iSfx < tl.sfx.Length && tl.sfx[iSfx].t <= now + 1e-4f) Sfx(tl.sfx[iSfx++]);
            while (iMusic < tl.music.Length && tl.music[iMusic].t <= now + 1e-4f) Music(tl.music[iMusic++]);
            if (Finished && sfxLoop.isPlaying) { sfxLoop.Stop(); loopId = null; }
        }

        DGActor Actor(string who) => who == "david" ? david : who == "goliath" ? goliath : null;

        // ---------------- acting ----------------
        void Act(DGActing a, int idx)
        {
            var A = Actor(a.who); if (!A) { Debug.LogWarning($"DG acting: unknown actor '{a.who}'"); return; }
            int i = A.Clip(a.clip);
            if (i < 0) { Debug.LogWarning($"DG acting: {a.who} has no clip '{a.clip}'"); return; }
            if (A == david && stoneThrown && A.cur == A.Clip("sling_release") && i != A.cur) stoneOn = false;   // spent stone would pop back into the pouch
            bool keepLoop = i == A.cur && A.loops != null && A.loops[i];       // idle -> idle: keep the loop running, no pop
            if (!keepLoop)
            {
                if (A.cur >= 0) { A.prev = A.cur; A.prevT0 = A.curT0; A.prevRate = A.curRate; A.blendT0 = a.t; A.blend = Mathf.Max(0.01f, a.blend); }
                A.cur = i; A.curT0 = a.t;
            }
            A.curRate = 1;
            if (!string.IsNullOrEmpty(a.face)) A.face = a.face;
            A.SetFace(i);
            // David's own stone appears at kneel_pick's pick5 marker (Desert(), below), not at the start of the clip
            if (A == david && a.clip == "sling_release") stoneThrown = true;
            A.moving = false;
            if (a.HasTarget)
            {
                float t1 = tl.duration;
                for (int k = idx + 1; k < tl.acting.Length; k++) if (tl.acting[k].who == a.who) { t1 = tl.acting[k].t; break; }
                A.moveFrom = A.pos; A.moveTo = new Vector2(a.to[0], a.to[1]); A.moveT0 = a.t; A.moveT1 = Mathf.Max(a.t + 0.05f, t1);
                A.moving = (A.moveTo - A.moveFrom).sqrMagnitude > 1e-8f;
                if (A.moving && DGAnimFacts.NaturalSpeed.TryGetValue(a.who + "_" + a.clip, out var vNat))
                {
                    float v = (A.moveTo - A.moveFrom).magnitude / (A.moveT1 - A.moveT0);
                    A.curRate = Mathf.Clamp(v / vNat, DGAnimFacts.MinRate, DGAnimFacts.MaxRate);   // feet roughly match the travel
                }
            }
        }

        void Move(DGActor A, float dt)
        {
            float want;
            bool travelling = false;
            if (A.moving)
            {
                float s = Mathf.Clamp01((now - A.moveT0) / (A.moveT1 - A.moveT0));
                A.pos = Vector2.Lerp(A.moveFrom, A.moveTo, s);
                travelling = s < 1;
                if (!travelling) A.moving = false;
            }
            if (travelling) { var d = A.moveTo - A.moveFrom; want = Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg; }
            else
            {
                var o = Actor(A.face);
                want = o && o != A ? Mathf.Atan2(o.pos.x - A.pos.x, o.pos.y - A.pos.y) * Mathf.Rad2Deg : 0;   // "viewer" = +Z
            }
            A.yaw = dt <= 0 && now > 0 ? A.yaw : Mathf.LerpAngle(A.yaw, want, now <= 0 ? 1 : 1 - Mathf.Exp(-dt / 0.12f));
        }

        // design (x right, z toward viewer, yaw about +y from +z toward +x) -> Unity local (-x, z, yaw mirrored)
        static Vector3 Local(Vector2 p, float y = 0) => new Vector3(-p.x, y, p.y);
        static void Place(DGActor A)
        {
            A.transform.localPosition = Local(A.pos);
            A.transform.localRotation = Quaternion.Euler(0, -A.yaw, 0);
        }

        void OnDestroy() { if (desertGraph.IsValid()) desertGraph.Destroy(); }

        // ---------------- desert: stones picked up, banners waving ----------------
        void Desert(float dt)
        {
            int kneel = david.Clip("kneel_pick");
            if (kneel >= 0 && david.cur == kneel)
            {
                float k = (now - david.curT0) * david.curRate;           // seconds into kneel_pick
                if (desertStones != null && desertStoneHideSec != null)
                    for (int i = 0; i < desertStones.Length && i < desertStoneHideSec.Length; i++)
                        if (desertStones[i] && k >= desertStoneHideSec[i]) desertStones[i].enabled = false;
                if (k >= stoneShowSec && !stoneThrown) stoneOn = true;
            }
            if (!desert || desertClips == null) return;
            desertT += dt;
            if (!Application.isPlaying || !desertAnimator)   // edit mode (DGPreview): SampleAnimation only works in the Editor
            {
                foreach (var c in desertClips) if (c) c.SampleAnimation(desert.gameObject, Mathf.Repeat(desertT, Mathf.Max(0.05f, c.length)));
                return;
            }
            if (!desertGraph.IsValid())
            {
                desertGraph = PlayableGraph.Create("DG_desert");
                desertGraph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
                var layers = AnimationLayerMixerPlayable.Create(desertGraph, desertClips.Length);
                AnimationPlayableOutput.Create(desertGraph, "banners", desertAnimator).SetSourcePlayable(layers);
                desertPlayables = new AnimationClipPlayable[desertClips.Length];
                for (int i = 0; i < desertClips.Length; i++)
                {
                    desertPlayables[i] = AnimationClipPlayable.Create(desertGraph, desertClips[i]);
                    desertPlayables[i].SetApplyFootIK(false);
                    desertGraph.Connect(desertPlayables[i], 0, layers, i);
                    layers.SetInputWeight(i, 1);
                }
            }
            for (int i = 0; i < desertPlayables.Length; i++)
                desertPlayables[i].SetTime(Mathf.Repeat(desertT, Mathf.Max(0.05f, desertClips[i].length)));
            desertGraph.Evaluate();
        }

        // ---------------- lines ----------------
        void Say(DGLine l)
        {
            if (seeking) return;
            var c = Clip($"voice/{L10n.Lang}/{l.id}");   // no clip (Arabic, or a line not voiced yet): subtitles only
            voice.Stop();
            if (c) { voice.clip = c; voice.volume = 1; voice.Play(); }
            Line = l;
            lineEnd = l.t + Mathf.Max(1.2f, c ? c.length : l.maxSec) + 0.35f;
            foreach (var n in tl.lines) if (n.t > l.t) { lineEnd = Mathf.Min(lineEnd, n.t - 0.05f); break; }
        }

        // ---------------- fx ----------------
        void Fx(DGFxCue f)
        {
            if (seeking) { seekFx.Add(f); return; }
            if (!fxEnabled) return;
            Transform at = transform;
            if (!string.IsNullOrEmpty(f.at))
            {
                int dot = f.at.IndexOf('.');
                var A = Actor(dot > 0 ? f.at.Substring(0, dot) : f.at);
                var b = A ? (dot > 0 ? A.Bone(f.at.Substring(dot + 1)) : A.transform) : null;
                if (b) at = b; else Debug.LogWarning($"DG fx {f.id}: cannot resolve '{f.at}'");
            }
            DGFx.Play(f.id, at, f.dur);
        }

        // ---------------- sfx ----------------
        void Sfx(DGSfxCue s)
        {
            if (seeking) { if (mix.TryGetValue(s.id, out var sm) && sm.loop) seekLoop = s; return; }
            // a looping sfx (sling_whoosh) runs until the next sfx of the same family (sling_snap) or the end
            if (loopId != null && Family(s.id) == Family(loopId)) { sfxLoop.Stop(); loopId = null; }
            var c = Clip("sfx/" + s.id); if (!c) return;
            mix.TryGetValue(s.id, out var m);
            float gain = m != null ? Mathf.Pow(10, m.gainDb / 20f) : 0.7f;
            if (m != null && m.loop) { sfxLoop.clip = c; sfxLoop.volume = gain; sfxLoop.Play(); loopId = s.id; }
            else sfx.PlayOneShot(c, gain);
        }
        static string Family(string id) { int u = id.IndexOf('_'); return u > 0 ? id.Substring(0, u) : id; }

        // ---------------- music: each cue starts at full level, the previous one fades out (cues.json) ----------------
        void Music(DGMusicCue m)
        {
            if (seeking) { seekMusic = m; return; }
            var c = Clip("music/" + m.cue); if (!c) return;
            var next = musicCur == musicA ? musicB : musicA;
            if (musicCur && musicCur.isPlaying) { musicOld = musicCur; musicOldFrom = musicCur.volume; musicFadeT = 0; }
            next.Stop(); next.clip = c; next.loop = false; next.volume = MusicVol(); next.Play();
            musicCur = next;
        }

        float MusicVol() => 0.8f * MusicLevel * voiceDuck;

        void Mix(float dt)
        {
            if (dt <= 0) return;
            voiceDuck = Mathf.MoveTowards(voiceDuck, voice.isPlaying ? 0.5f : 1f, dt * 2.5f);   // ~6 dB under voice
            if (musicCur && musicCur.isPlaying) musicCur.volume = MusicVol();
            if (musicOld)
            {
                musicFadeT += dt;
                float k = Mathf.Clamp01(musicFadeT / Mathf.Max(0.05f, cues != null ? cues.crossfadeSec : 0.6f));
                musicOld.volume = musicOldFrom * (1 - k);
                if (k >= 1) { musicOld.Stop(); musicOld = null; }
            }
        }

        // ---------------- demo: printed page under the actors + shot-list camera ----------------
        void BuildDemoPage()
        {
            if (!demoPage) return;
            // A4 page = 1.24 x 1.754 art units; the art rectangle's bottom edge (the figures' feet line, page px 1510)
            // is local z = 0, the page top is at z = -1.510 (away from the viewer). Same layout as the Blender preview.
            var m = new Mesh { name = "DGDemoPage" };
            float x0 = 0.62f, zTop = -1.510f, zBot = 0.244f, y = -0.001f;
            m.vertices = new[] { new Vector3(x0, y, zBot), new Vector3(-x0, y, zBot), new Vector3(-x0, y, zTop), new Vector3(x0, y, zTop) };
            m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };   // local +x = page left
            m.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
            m.RecalculateBounds();
            var mf = demoPage.GetComponent<MeshFilter>(); if (mf) mf.sharedMesh = m;
        }
        // Sand ground (CONTRACT §12.4): the same page rectangle as the demo page, 0.0005 above the paper (the desert
        // pieces sink 0.002 into it). UV0 = design (x, z); DGGround maps it to the mask (page frame) and the scan (art rect).
        void BuildGround()
        {
            if (!ground) return;
            var m = new Mesh { name = "DGGround" };
            float x0 = 0.62f, zTop = -1.510f, zBot = 0.244f, y = 0.0005f;
            m.vertices = new[] { new Vector3(x0, y, zBot), new Vector3(-x0, y, zBot), new Vector3(-x0, y, zTop), new Vector3(x0, y, zTop) };
            m.uv = new[] { new Vector2(-x0, zBot), new Vector2(x0, zBot), new Vector2(x0, zTop), new Vector2(-x0, zTop) };   // local +x = design -x
            m.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
            m.RecalculateBounds();
            var mf = ground.GetComponent<MeshFilter>(); if (mf) mf.sharedMesh = m;
        }

        public void ShowDemoPage(bool on) { if (demoPage) demoPage.gameObject.SetActive(on); }

        Vector3 ActorPoint(DGActor A) => transform.TransformPoint(Local(A.pos, A.height * 0.55f));

        void DriveCamera(Camera cam)
        {
            var s = Shot; if (s == null || s.camera == null) return;
            var c = s.camera;
            Vector3 target;
            if (c.target == "david") target = ActorPoint(david);
            else if (c.target == "goliath") target = ActorPoint(goliath);
            else if (c.target == "stone" && david.Bone("stone")) target = david.Bone("stone").position;
            else { var mid = (david.pos + goliath.pos) / 2; target = transform.TransformPoint(Local(mid, 0.28f)); }
            if (c.type == "fixed")
            {
                if (camFixedFor != s.t0) { camFixedFor = s.t0; camFixedTarget = target; }
                target = camFixedTarget;
            }
            float yaw = c.yawDeg + (c.type == "orbit" ? 8f * (now - s.t0) : 0);
            float dist = c.dist;
            // the hints are framed for 16:9 with a ~62° horizontal view; on a portrait phone pull back instead of
            // widening the lens past 60° (LESSONS: portrait battle camera)
            float aspect = Mathf.Max(0.3f, cam.aspect), half = 31f * Mathf.Deg2Rad;
            float vfov = 2 * Mathf.Atan(Mathf.Tan(half) / aspect) * Mathf.Rad2Deg;
            if (vfov > 60) { dist *= Mathf.Tan(half) / (Mathf.Tan(30 * Mathf.Deg2Rad) * aspect); vfov = 60; }
            cam.fieldOfView = Mathf.Max(30, vfov);
            var tl_ = transform.InverseTransformPoint(target);                                  // design point (local)
            var design = new Vector2(-tl_.x, tl_.z);
            float a = yaw * Mathf.Deg2Rad;
            var cpos = transform.TransformPoint(Local(design + new Vector2(Mathf.Sin(a), Mathf.Cos(a)) * dist, c.height * Mathf.Max(1, dist / Mathf.Max(0.01f, c.dist))));
            cam.transform.SetPositionAndRotation(cpos, Quaternion.LookRotation(target - cpos, Vector3.up));
        }
    }
}
