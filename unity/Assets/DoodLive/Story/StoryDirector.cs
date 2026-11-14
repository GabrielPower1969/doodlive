// StoryDirector plays any story pack's timeline (docs/STORY-ARCHITECTURE.md, e.g. docs/esther/CONTRACT.md §5) on its
// cast of DGActors and its set: acting (clips with cross-fades, moves, base heights), lines (voice in the current
// language + subtitle data), props (show / hide nodes), fx (DGFx.Play), sfx and music (cue cross-fades), and the set's
// looping clips (curtains). It owns performance time: pause freezes animation, audio and effects at the same instant.
//
// Generalised from DavidGoliath.DGDirector, which stays as pack #1's own director until it migrates here.
// Space: this transform is DGFx.Stage, local unit = 1 art width, page at local y = 0, local +Z = toward the viewer
// (page bottom); design x maps to local -x (glTFast mirrors X, LESSONS L26).
using System.Collections.Generic;
using DoodLive.DavidGoliath;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace DoodLive.Story
{
    public class StoryDirector : MonoBehaviour, IStoryPlayer
    {
        [Tooltip("Story id = folder under assets/ and Resources/Stories/ (e.g. esther)")]
        public string storyId;
        public DGActor[] actors;
        [Tooltip("design.json sheetX per actor (same order): where each figure is drawn, so it stands up from its drawing")]
        public float[] sheetX;
        [Tooltip("Identity pivot above actors and set; DGFx shakes it")]
        public Transform shake;
        public MeshRenderer demoPage;
        [Tooltip("Set root (e.g. palace.glb instance)")]
        public Transform set;
        public Animator setAnimator;
        public AnimationClip[] setClips;
        [Tooltip("Page-coloured materials (characters + set): the controller puts the scanned art rectangle on _BaseMap")]
        public Material[] pageMaterials;
        [Tooltip("The pack's sample colouring (assets/<id>/sheet/demo-colored.png) for the home screen demo")]
        public Texture2D demoTexture;
        public string titleZh, titleEn;

        string ResDir => "Stories/" + storyId + "/";
        public string StoryId => storyId;

        // ---------------- state the UI reads ----------------
        public bool Running { get; private set; }
        public bool Finished => Running && tl != null && now >= tl.duration;
        public bool Paused { get; set; }
        public bool Hold { get; set; }
        public float Now => now;
        public DGTimeline Timeline => tl;
        public DGLine Line { get; private set; }
        public float LineAge => Line != null ? now - Line.t : 0;
        public DGShot Shot { get; private set; }
        public float ShotAge => Shot != null ? now - Shot.t0 : 0;
        public float MusicGain { get; set; } = 1f;
        public Camera Cinematic { get; set; }

        DGTimeline tl; DGCues cues;
        VoiceCast cast;                                            // docs/VOICE-SYSTEM.md: the voices installed for this play
        // music loop sections and ambience stop cues (story packs from Ruth on; absent keys = old behaviour)
        [System.Serializable] class CueLoop { public string cue; public float loopStart, loopEnd; }
        [System.Serializable] class CueLoops { public CueLoop[] cues; }
        [System.Serializable] class SfxStop { public string id, stopAtCue; public float fadeOutSec; }
        [System.Serializable] class SfxStops { public SfxStop[] sfx; }
        readonly Dictionary<string, CueLoop> cueLoops = new Dictionary<string, CueLoop>();
        readonly Dictionary<string, SfxStop> sfxStops = new Dictionary<string, SfxStop>();
        float sfxLoopFade = -1, sfxLoopFrom;
        readonly Dictionary<string, DGSfxMixEntry> mix = new Dictionary<string, DGSfxMixEntry>();
        readonly Dictionary<string, AudioClip> clipCache = new Dictionary<string, AudioClip>();
        readonly Dictionary<string, DGActor> byId = new Dictionary<string, DGActor>();
        readonly Dictionary<string, float> baseY = new Dictionary<string, float>();
        Dictionary<string, Transform> setNodes;
        float now, lineEnd, setT;
        int iAct, iLine, iFx, iSfx, iMusic, iProp;
        bool frozen;
        AudioSource voice, sfx, sfxLoop, musicA, musicB, musicCur, musicOld; string loopId;
        float voiceDuck = 1, musicOldFrom, musicFadeT, camFixedFor = -1; Vector3 camFixedTarget;
        PlayableGraph setGraph; AnimationClipPlayable[] setPlayables;
        [System.NonSerialized] public bool fxEnabled = true;

        void Awake() { Init(); if (Application.isPlaying) VoiceBank.Prepare(storyId, L10n.Lang); }

        void Init()
        {
            if (voice) return;
            voice = NewSource("voice"); sfx = NewSource("sfx"); sfxLoop = NewSource("sfxLoop"); sfxLoop.loop = true;
            musicA = NewSource("musicA"); musicB = NewSource("musicB");
            BuildDemoPage(); ShowDemoPage(false);
            byId.Clear(); if (actors != null) foreach (var a in actors) if (a) byId[a.id] = a;
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
            if (!j) { Debug.LogError($"Story {storyId}: Resources/{ResDir}timeline.json missing (run DoodLive > Setup Project)"); return false; }
            cast = VoiceBank.Resolve(storyId, L10n.Lang, j.text);
            tl = StoryRetime.Load(j.text, VoiceBank.Durations(cast));
            var m = Resources.Load<TextAsset>(ResDir + "sfx_mix");
            if (m) foreach (var e in JsonUtility.FromJson<DGSfxMix>(m.text).sfx) mix[e.id] = e;
            sfxStops.Clear(); if (m) { var ss = JsonUtility.FromJson<SfxStops>(m.text); if (ss?.sfx != null) foreach (var e in ss.sfx) if (!string.IsNullOrEmpty(e.stopAtCue)) sfxStops[e.id] = e; }
            var c = Resources.Load<TextAsset>(ResDir + "music_cues");
            cues = c ? JsonUtility.FromJson<DGCues>(c.text) : new DGCues();
            cueLoops.Clear(); if (c) { var cl = JsonUtility.FromJson<CueLoops>(c.text); if (cl?.cues != null) foreach (var e in cl.cues) if (e.loopEnd > e.loopStart + 0.2f) cueLoops[e.cue] = e; }
            Debug.Log($"Story {storyId}: {tl.duration} s, cast [{string.Join(",", tl.cast ?? new string[0])}], {tl.acting.Length} acting, {tl.lines.Length} lines, {tl.fx.Length} fx, {tl.sfx.Length} sfx, {tl.music.Length} music, {tl.props.Length} props");
            return true;
        }

        AudioClip Clip(string path)
        {
            if (!clipCache.TryGetValue(path, out var c)) { c = Resources.Load<AudioClip>(ResDir + path); clipCache[path] = c; if (!c) Debug.LogWarning($"Story {storyId}: missing audio {path}"); }
            return c;
        }

        // ---------------- control ----------------
        public void Begin()
        {
            tl = null; if (!LoadData()) return;   // re-read: the installed voices may have changed (VOICE-SYSTEM.md)
            Init();
            StopAudio(); DGFx.StopAll();
            DGFx.Stage = transform; DGFx.ShakeTarget = shake; if (fxEnabled) DGFx.Prewarm();
            now = 0; lineEnd = 0; iAct = iLine = iFx = iSfx = iMusic = iProp = 0; Line = null; Shot = null; setT = 0;
            Paused = false; Hold = false; frozen = false; camFixedFor = -1; baseY.Clear();
            for (int i = 0; i < actors.Length; i++)
                if (actors[i]) ResetActor(actors[i], sheetX != null && i < sheetX.Length ? sheetX[i] : 0);
            Running = true;
            gameObject.SetActive(true);
            Step(0);
        }

        void ResetActor(DGActor a, float x)
        {
            a.Init();
            foreach (var r in a.GetComponentsInChildren<Renderer>(true)) r.enabled = true;   // undo last run's props (an actor led away)
            a.pos = new Vector2(x, 0); a.yaw = 0; a.face = "viewer"; a.cur = a.prev = -1; a.moving = false; a.curRate = 1;
            int idle = a.Clip("idle"); if (idle < 0) idle = a.Clip("sit_idle");
            a.cur = Mathf.Max(0, idle); a.curT0 = 0; a.SetFace(a.cur);
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
                var m = seekMusic; seekMusic = null; PlayMusic(m);
                if (musicCur && musicCur.clip) musicCur.time = Mathf.Clamp(t - m.t, 0, Mathf.Max(0, musicCur.clip.length - 0.05f));
            }
        }

        public void Stop()
        {
            Running = false; Line = null; Shot = null;
            StopAudio(); DGFx.StopAll(); DGFx.Paused = false;
            Cinematic = null;
        }

        public void EditorInit() { Init(); fxEnabled = false; }
        public void EditorStep(float dt) { if (Running) Step(dt); }
        public void TogglePause() { if (Running && !Finished) Paused = !Paused; }

        void StopAudio()
        {
            foreach (var s in new[] { voice, sfx, sfxLoop, musicA, musicB }) if (s) s.Stop();
            musicCur = musicOld = null; loopId = null; musicCueId = null; if (sfxLoopFade > 0 && sfxLoop) sfxLoop.volume = sfxLoopFrom; sfxLoopFade = -1;
        }

        void SetFrozen(bool f)
        {
            if (f == frozen) return;
            frozen = f; DGFx.Paused = f;
            foreach (var s in new[] { voice, sfx, sfxLoop, musicA, musicB }) { if (!s) continue; if (f) s.Pause(); else s.UnPause(); }
        }

        void Update()
        {
            if (!Running) return;
            SetFrozen(Paused || Hold);
            Step(frozen ? 0 : Time.deltaTime);
        }

        void Step(float dt)
        {
            if (!Finished) now = Mathf.Min(tl.duration, now + dt);
            Events();
            Shot = tl.ShotAt(now);
            if (Line != null && now > lineEnd) Line = null;
            foreach (var a in actors) { if (!a) continue; Move(a, dt); Place(a); a.Evaluate(now); }
            LipSync(dt);
            SetClips(dt);
            Mix(dt);
            if (Cinematic) DriveCamera(Cinematic);
        }

        void Events()
        {
            const float e = 1e-4f;
            while (iProp < tl.props.Length && tl.props[iProp].t <= now + e) Prop(tl.props[iProp++]);
            while (iAct < tl.acting.Length && tl.acting[iAct].t <= now + e) Act(tl.acting[iAct], iAct++);
            while (iLine < tl.lines.Length && tl.lines[iLine].t <= now + e) Say(tl.lines[iLine++]);
            while (iFx < tl.fx.Length && tl.fx[iFx].t <= now + e) Fx(tl.fx[iFx++]);
            while (iSfx < tl.sfx.Length && tl.sfx[iSfx].t <= now + e) Sfx(tl.sfx[iSfx++]);
            while (iMusic < tl.music.Length && tl.music[iMusic].t <= now + e) PlayMusic(tl.music[iMusic++]);
            if (Finished && sfxLoop.isPlaying) { sfxLoop.Stop(); loopId = null; }
        }

        DGActor Actor(string who) => who != null && byId.TryGetValue(who, out var a) ? a : null;

        // ---------------- props: "<actor>/<node>" or "<set>/<node>" ----------------
        Transform Node(string path)
        {
            if (string.IsNullOrEmpty(path)) return null;
            int sl = path.IndexOfAny(new[] { '/', '.' });
            string owner = sl > 0 ? path.Substring(0, sl) : path, leaf = sl > 0 ? path.Substring(sl + 1) : null;
            var A = Actor(owner);
            if (A) return leaf == null ? A.transform : A.Bone(leaf);
            if (owner == "stage") return transform;
            if (set && (owner == tl?.set || owner == set.name))
            {
                if (leaf == null) return set;
                if (setNodes == null) { setNodes = new Dictionary<string, Transform>(); foreach (var t in set.GetComponentsInChildren<Transform>(true)) if (!setNodes.ContainsKey(t.name)) setNodes[t.name] = t; }
                return setNodes.TryGetValue(leaf, out var n) ? n : null;
            }
            if (set && setNodes == null) { setNodes = new Dictionary<string, Transform>(); foreach (var t in set.GetComponentsInChildren<Transform>(true)) if (!setNodes.ContainsKey(t.name)) setNodes[t.name] = t; }
            return set && setNodes.TryGetValue(owner, out var n2) ? n2 : null;   // bare set node name ("throne", "table")
        }

        void Prop(DGProp p)
        {
            var n = Node(p.node);
            if (!n) { Debug.LogWarning($"Story {storyId} prop: no node '{p.node}'"); return; }
            foreach (var r in n.GetComponentsInChildren<Renderer>(true)) r.enabled = p.show;
        }

        // ---------------- acting ----------------
        void Act(DGActing a, int idx)
        {
            var A = Actor(a.who); if (!A) { Debug.LogWarning($"Story {storyId} acting: unknown actor '{a.who}'"); return; }
            int i = A.Clip(a.clip);
            if (i < 0) { Debug.LogWarning($"Story {storyId} acting: {a.who} has no clip '{a.clip}'"); return; }
            bool keepLoop = i == A.cur && A.loops != null && A.loops[i];
            if (!keepLoop)
            {
                if (A.cur >= 0) { A.prev = A.cur; A.prevT0 = A.curT0; A.prevRate = A.curRate; A.blendT0 = a.t; A.blend = Mathf.Max(0.01f, a.blend); }
                A.cur = i; A.curT0 = a.t;
            }
            A.curRate = 1;
            if (!string.IsNullOrEmpty(a.face)) A.face = a.face;
            A.SetFace(i);
            if (!float.IsNaN(a.y)) baseY[A.id] = a.y;
            A.moving = false;
            if (a.HasTarget)
            {
                float t1 = tl.duration;
                for (int k = idx + 1; k < tl.acting.Length; k++) if (tl.acting[k].who == a.who) { t1 = tl.acting[k].t; break; }
                A.moveFrom = A.pos; A.moveTo = new Vector2(a.to[0], a.to[1]); A.moveT0 = a.t;
                // travel at the clip's natural speed (clips.json naturalSpeed) so the feet match the ground; if the next
                // beat comes sooner, play the clip faster (up to 1.6x). Non-locomotion clips with a mark glide gently.
                float dist = (A.moveTo - A.moveFrom).magnitude, vNat = A.Speed(i);
                float natural = vNat > 0 ? dist / vNat : Mathf.Max(0.6f, dist / 0.12f);
                float avail = Mathf.Max(0.3f, t1 - a.t);
                if (vNat > 0 && natural > avail) A.curRate = Mathf.Clamp(natural / avail, 1f, 1.6f);
                A.moveT1 = a.t + Mathf.Max(0.05f, natural / A.curRate);
                A.moving = dist > 1e-4f;
                if (a.t <= 0.01f) { A.pos = A.moveTo; A.moving = false; Place(A); }   // a mark at t = 0 is the starting place, not a walk
            }
        }

        void Move(DGActor A, float dt)
        {
            float want; bool travelling = false;
            if (A.moving)
            {
                float s = Mathf.Clamp01((now - A.moveT0) / (A.moveT1 - A.moveT0));
                // locomotion: constant speed (the feet are planted at a constant cadence); other clips: eased glide
                float e = A.Speed(A.cur) > 0 ? s : s * s * (3 - 2 * s);
                A.pos = Vector2.Lerp(A.moveFrom, A.moveTo, e);
                travelling = s < 1;
                if (!travelling)
                {   // arrived: a locomotion clip hands over to the idle so nobody walks on the spot
                    A.moving = false;
                    if (A.Speed(A.cur) > 0)
                    {
                        int idle = A.Clip("idle"); if (idle < 0) idle = A.Clip("sit_idle");
                        if (idle >= 0) { A.prev = A.cur; A.prevT0 = A.curT0; A.prevRate = A.curRate; A.blendT0 = now; A.blend = 0.3f; A.cur = idle; A.curT0 = now; A.curRate = 1; A.SetFace(idle); }
                    }
                }
            }
            if (travelling) { var d = A.moveTo - A.moveFrom; want = Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg + (A.Backwards(A.cur) ? 180 : 0); }
            else
            {
                var o = Actor(A.face);
                Vector2 target = o && o != A ? o.pos : Vector2.zero; bool has = o && o != A;
                if (!has && A.face != null && A.face != "viewer") { var n = Node(A.face); if (n) { var l = transform.InverseTransformPoint(n.position); target = new Vector2(-l.x, l.z); has = true; } }
                want = has ? Mathf.Atan2(target.x - A.pos.x, target.y - A.pos.y) * Mathf.Rad2Deg : 0;
            }
            A.yaw = dt <= 0 && now > 0 ? A.yaw : Mathf.LerpAngle(A.yaw, want, now <= 0 ? 1 : 1 - Mathf.Exp(-dt / 0.15f));
        }

        static Vector3 Local(Vector2 p, float y = 0) => new Vector3(-p.x, y, p.y);
        void Place(DGActor A)
        {
            baseY.TryGetValue(A.id, out float y);
            A.transform.localPosition = Local(A.pos, y);
            A.transform.localRotation = Quaternion.Euler(0, -A.yaw, 0);
        }

        // ---------------- set: looping clips (curtains) ----------------
        void SetClips(float dt)
        {
            if (!set || setClips == null || setClips.Length == 0) return;
            setT += dt;
            if (!Application.isPlaying || !setAnimator)
            {
                foreach (var c in setClips) if (c) c.SampleAnimation(set.gameObject, Mathf.Repeat(setT, Mathf.Max(0.05f, c.length)));
                return;
            }
            if (!setGraph.IsValid())
            {
                setGraph = PlayableGraph.Create("Story_set_" + storyId);
                setGraph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
                var layers = AnimationLayerMixerPlayable.Create(setGraph, setClips.Length);
                AnimationPlayableOutput.Create(setGraph, "set", setAnimator).SetSourcePlayable(layers);
                setPlayables = new AnimationClipPlayable[setClips.Length];
                for (int i = 0; i < setClips.Length; i++)
                {
                    setPlayables[i] = AnimationClipPlayable.Create(setGraph, setClips[i]);
                    setPlayables[i].SetApplyFootIK(false);
                    setGraph.Connect(setPlayables[i], 0, layers, i);
                    layers.SetInputWeight(i, 1);
                }
            }
            for (int i = 0; i < setPlayables.Length; i++) setPlayables[i].SetTime(Mathf.Repeat(setT, Mathf.Max(0.05f, setClips[i].length)));
            setGraph.Evaluate();
        }

        void OnDestroy() { if (setGraph.IsValid()) setGraph.Destroy(); }

        // ---------------- lines ----------------
        void Say(DGLine l)
        {
            if (seeking) return;
            var c = cast != null ? cast.Clip(l.id) : Clip($"voice/{(L10n.IsZh ? "zh" : "en")}/{l.id}");
            voice.Stop();
            if (c) { voice.clip = c; voice.volume = 1; voice.Play(); }
            Line = l;
            lineEnd = l.t + Mathf.Max(1.2f, c ? c.length : l.maxSec) + 0.35f;
            foreach (var n in tl.lines) if (n.t > l.t) { lineEnd = Mathf.Min(lineEnd, n.t - 0.05f); break; }
        }

        // ---------------- lip sync: the speaker's jaw follows the loudness of the voice ----------------
        readonly float[] lipBuf = new float[256]; float lipLevel;
        void LipSync(float dt)
        {
            if (Line == null || !voice || !voice.isPlaying) { lipLevel = 0; return; }
            var A = Actor(Line.who); if (!A) return;
            var jaw = A.Bone("jaw"); if (!jaw) return;
            voice.GetOutputData(lipBuf, 0);
            float sum = 0; for (int i = 0; i < lipBuf.Length; i++) sum += lipBuf[i] * lipBuf[i];
            float rms = Mathf.Sqrt(sum / lipBuf.Length);
            float target = Mathf.Clamp01((rms - 0.012f) * 7f);                          // ~-38 dBFS opens, ~-17 dBFS fully
            lipLevel = Mathf.Lerp(lipLevel, target, dt > 0 ? 1 - Mathf.Exp(-dt / 0.045f) : 0);
            jaw.localRotation *= Quaternion.Euler(14f * lipLevel, 0, 0);                  // on top of the clip's pose
        }

        // ---------------- fx / sfx / music ----------------
        void Fx(DGFxCue f)
        {
            if (seeking) { seekFx.Add(f); return; }
            if (!fxEnabled) return;
            var at = Node(f.at);
            if (!at) { Debug.LogWarning($"Story {storyId} fx {f.id}: cannot resolve '{f.at}'"); at = transform; }
            if (!string.IsNullOrEmpty(f.to)) { var to = Node(f.to); if (to) StoryFxStage.BeamTarget = to; }
            DGFx.Play(f.id, at, f.dur);
        }

        void Sfx(DGSfxCue s)
        {
            if (seeking) { if (mix.TryGetValue(s.id, out var sm) && sm.loop) seekLoop = s; return; }
            var c = Clip("sfx/" + s.id); if (!c) return;
            mix.TryGetValue(s.id, out var m);
            float gain = m != null ? Mathf.Pow(10, m.gainDb / 20f) : 0.7f;
            if (m != null && m.loop) { sfxLoopFade = -1; sfxLoop.clip = c; sfxLoop.volume = gain; sfxLoop.Play(); loopId = s.id; }
            else sfx.PlayOneShot(c, gain);
        }

        void PlayMusic(DGMusicCue m)
        {
            if (seeking) { seekMusic = m; return; }
            var c = Clip("music/" + m.cue); if (!c) return;
            var next = musicCur == musicA ? musicB : musicA;
            if (musicCur && musicCur.isPlaying) { musicOld = musicCur; musicOldFrom = musicCur.volume; musicFadeT = 0; }
            next.Stop(); next.clip = c; next.loop = false; next.volume = MusicVol(); next.Play();
            musicCur = next; musicCueId = m.cue;
            if (sfxLoop.isPlaying && loopId != null && sfxStops.TryGetValue(loopId, out var st) && st.stopAtCue == m.cue)
            { sfxLoopFade = Mathf.Max(0.05f, st.fadeOutSec > 0 ? st.fadeOutSec : 1f); sfxLoopFrom = sfxLoop.volume; }
        }

        string musicCueId;
        float MusicVol() => 0.8f * MusicGain * voiceDuck;

        void Mix(float dt)
        {
            if (dt <= 0) return;
            voiceDuck = Mathf.MoveTowards(voiceDuck, voice.isPlaying ? 0.5f : 1f, dt * 2.5f);
            if (musicCur && musicCur.isPlaying)
            {
                musicCur.volume = MusicVol();
                // stretched scene: loop the cue's quiet final section until the next cue (cues.json loopStart/loopEnd)
                if (musicCueId != null && cueLoops.TryGetValue(musicCueId, out var lp) && musicCur.time >= lp.loopEnd) musicCur.time -= lp.loopEnd - lp.loopStart;
            }
            if (sfxLoopFade > 0)
            {
                float v = sfxLoop.volume - sfxLoopFrom * dt / sfxLoopFade;
                if (v <= 0) { sfxLoop.Stop(); sfxLoop.volume = sfxLoopFrom; sfxLoopFade = -1; loopId = null; } else sfxLoop.volume = v;
            }
            if (musicOld)
            {
                musicFadeT += dt;
                float k = Mathf.Clamp01(musicFadeT / Mathf.Max(0.05f, cues != null ? cues.crossfadeSec : 0.6f));
                musicOld.volume = musicOldFrom * (1 - k);
                if (k >= 1) { musicOld.Stop(); musicOld = null; }
            }
        }

        // ---------------- demo: printed page under the stage + shot-list camera ----------------
        void BuildDemoPage()
        {
            if (!demoPage) return;
            var m = new Mesh { name = "StoryDemoPage" };
            float x0 = 0.62f, zTop = -1.510f, zBot = 0.244f, y = -0.001f;   // A4 in art units; z = 0 = art rectangle bottom
            m.vertices = new[] { new Vector3(x0, y, zBot), new Vector3(-x0, y, zBot), new Vector3(-x0, y, zTop), new Vector3(x0, y, zTop) };
            m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
            m.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
            m.RecalculateBounds();
            var mf = demoPage.GetComponent<MeshFilter>(); if (mf) mf.sharedMesh = m;
        }

        public void ShowDemoPage(bool on) { if (demoPage) demoPage.gameObject.SetActive(on); }

        Vector3 Target(string id)
        {
            var A = Actor(id);
            if (A) { baseY.TryGetValue(A.id, out float y); return transform.TransformPoint(Local(A.pos, y + A.height * 0.55f)); }
            if (id == "all" || id == "both" || string.IsNullOrEmpty(id))
            {
                Vector2 sum = Vector2.zero; int n = 0; foreach (var a in actors) if (a) { sum += a.pos; n++; }
                return transform.TransformPoint(Local(n > 0 ? sum / n : Vector2.zero, 0.2f));
            }
            var node = Node(id);
            return node ? node.position + transform.up * 0.08f * transform.lossyScale.y : transform.position;
        }

        void DriveCamera(Camera cam)
        {
            var s = Shot; if (s == null || s.camera == null) return;
            var c = s.camera;
            var target = Target(c.target);
            if (c.type == "fixed")
            {
                if (camFixedFor != s.t0) { camFixedFor = s.t0; camFixedTarget = target; }
                target = camFixedTarget;
            }
            float yaw = c.yawDeg + (c.type == "orbit" ? 6f * (now - s.t0) : 0);
            float dist = c.dist;
            float aspect = Mathf.Max(0.3f, cam.aspect), half = 31f * Mathf.Deg2Rad;
            float vfov = 2 * Mathf.Atan(Mathf.Tan(half) / aspect) * Mathf.Rad2Deg;
            if (vfov > 60) { dist *= Mathf.Tan(half) / (Mathf.Tan(30 * Mathf.Deg2Rad) * aspect); vfov = 60; }
            cam.fieldOfView = Mathf.Max(30, vfov);
            var tl_ = transform.InverseTransformPoint(target);
            var design = new Vector2(-tl_.x, tl_.z);
            float a = yaw * Mathf.Deg2Rad;
            var cpos = transform.TransformPoint(Local(design + new Vector2(Mathf.Sin(a), Mathf.Cos(a)) * dist, tl_.y + c.height * Mathf.Max(1, dist / Mathf.Max(0.01f, c.dist))));
            // ease the camera between shots instead of cutting hard (smoother demo video)
            float k = now - s.t0 < 0.6f ? 1 - Mathf.Exp(-Time.deltaTime / 0.18f) : 1;
            cam.transform.position = Vector3.Lerp(cam.transform.position, cpos, k);
            cam.transform.rotation = Quaternion.Slerp(cam.transform.rotation, Quaternion.LookRotation(target - cpos, Vector3.up), k);
        }
    }
}
