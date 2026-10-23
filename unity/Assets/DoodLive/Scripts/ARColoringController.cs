// DoodLive app flow — the state machine from docs/UX-PLAN.md §3 (Unity is the reference; web/app.js mirrors it).
//
//   Home ─► Permission ─► Scan.Search ─► Scan.Locked(1.5 s) ─► Reveal(≤4 s, uninterruptible) ─► Live.Idle
//                            │  └─30 s─► Scan.Help                                              │  ▲
//                            └──────────────────────────────── Live.Lost ◄── tracking lost 1.0 s ─┘  │
//                                                   Live.Blow / Live.Read / Live.Greet ───────────────┘
//   Paused: app in background — music fades out 0.3 s, back in 0.6 s, no re-scan.
//
// Stop/go rule: stop where the child must act (press, aim), go where the system can tell (locked 1.5 s, action
// finished). Every automatic step has visible progress and a timeout with a concrete hint. UI motion ≤ 300 ms,
// character motion ≤ 1.5 s; only Reveal blocks input. Sound: voice > sfx > music; voices never overlap.
//
// Capture: the camera frame is copied in screen space (ARCameraBackground material -> RenderTexture), so the tracked
// sheet's corners project with Camera.WorldToScreenPoint; the 4 printed markers are refined in that frame
// (PageWarp.RefineMarkers) and the art rectangle is warped to 1024².
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
#if UNITY_ANDROID
using UnityEngine.Android;
#endif

namespace DoodLive
{
    public partial class ARColoringController : MonoBehaviour
    {
        public const int TexSize = 1024;

        [Header("AR")]
        public ARSession session;
        public ARTrackedImageManager trackedImages;
        public ARCameraManager cameraManager;
        public ARCameraBackground cameraBackground;
        public Camera arCamera;

        [Header("Angel")]
        public Animator angel;
        public Material[] pageMaterials;
        public Texture2D demoTexture;
        [Tooltip("Angel height on the sheet, as a fraction of the art width (web: 0.75)")]
        public float scaleOnSheet = 0.75f;

        [Header("Sound")]
        public AudioSource sfx, voice, music;
        public float musicBed = 0.22f;
        public AudioClip fanfare, chime, hello, swell;
        public AudioClip[] lines;           // Blow lines, rotate
        public AudioClip[] greets;          // idle greetings (fly / wow / laugh)
        [Header("English voice (Gabriel, web/assets/voice/gabriel-en)")]
        public AudioClip helloEn; public AudioClip[] linesEn, greetsEn;
        AudioClip Hello => !L10n.IsZh && helloEn ? helloEn : hello;
        AudioClip[] Lines => !L10n.IsZh && linesEn != null && linesEn.Length > 0 ? linesEn : lines;
        AudioClip[] Greets => !L10n.IsZh && greetsEn != null && greetsEn.Length > 0 ? greetsEn : greets;

        // ---------------- timings (seconds) — UX-PLAN §3/§4 ----------------
        const float LockSeconds = 1.5f, HelpAfter = 30f, LostAfter = 1.0f, GreetAfter = 20f, GreetEvery = 25f, GreetMax = 2;
        const float RevealSeconds = 1.4f, BlowSeconds = 3.3f, ReadStep = 1.3f, HintAfter = 5f, GateHold = 2f;

        public enum State { Home, Permission, ScanSearch, ScanLocked, ScanHelp, Reveal, LiveIdle, LiveBlow, LiveRead, LiveGreet, LiveLost }
        public State state = State.Home;
        float stateT;                       // seconds in the current state
        bool paused;

        Template tpl;
        Transform holder;
        Texture2D pageTex;
        Color32[] rawPx, cleanPx;
        bool showLines, arReady, arUnsupported, showMode, capturing, moreOpen, muted, haptics = true;
        string statusKey = "", statusArg = "";
        float lockedFor, untracked, idleSince, lastGreet, lastTouch; int greetCount, lineIdx, greetIdx;
        static readonly int BlowId = Animator.StringToHash("Blow"), BlowState = Animator.StringToHash("Blow");

        public static string Fingerprint => Resources.Load<TextAsset>("build_fingerprint")?.text.Trim() ?? Application.version;

        // =====================================================================================================
        void Start()
        {
            Debug.Log($"DoodLive build {Fingerprint}");          // scripts/install-apk.sh greps this line
            tpl = Template.Load();
            pageTex = new Texture2D(TexSize, TexSize, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = "ScannedPage" };
            holder = new GameObject("AngelHolder").transform;
            angel.transform.SetParent(holder, false);
            angel.gameObject.SetActive(false);
            if (session) session.enabled = false;
            Screen.sleepTimeout = SleepTimeout.NeverSleep;
            muted = PlayerPrefs.GetInt("muted", 0) == 1; AudioListener.volume = muted ? 0 : 1;
            haptics = PlayerPrefs.GetInt("haptics", 1) == 1; musicBed = PlayerPrefs.GetFloat("musicBed", musicBed);
            MakeCues();
            Go(State.Home);
        }

        void Go(State s)
        {
            if (state == s) return;
            Debug.Log($"DoodLive state {state} -> {s}");
            if (state == State.Reveal && s == State.LiveIdle) Buzz(30);   // one soft bump when she lands (screen 05)
            state = s; stateT = 0;
            switch (s)
            {
                case State.Home: statusKey = ""; angel.gameObject.SetActive(false); break;
                case State.Permission: statusKey = "openingCam"; StartCoroutine(Boot()); break;
                case State.ScanSearch: showMode = false; lockedFor = 0; angel.gameObject.SetActive(false); statusKey = "fit"; break;
                case State.ScanLocked: statusKey = "found"; Cue(cueLock); break;
                case State.ScanHelp: statusKey = ""; break;
                case State.Reveal: StartReveal(); break;
                case State.LiveIdle: idleSince = Time.time; if (statusKey != "lost") statusKey = "tap"; break;
                case State.LiveLost: statusKey = "lost"; Cue(cueLost); break;
            }
        }

        IEnumerator Boot()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera))
            {
                bool answered = false;
                var cb = new PermissionCallbacks();
                cb.PermissionGranted += _ => answered = true; cb.PermissionDenied += _ => answered = true; cb.PermissionDeniedAndDontAskAgain += _ => answered = true;
                Permission.RequestUserPermission(Permission.Camera, cb);
                while (!answered) yield return null;
            }
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera)) { statusKey = "noPerm"; Go(State.Home); statusKey = "noPerm"; yield break; }
#endif
            if (ARSession.state == ARSessionState.None || ARSession.state == ARSessionState.CheckingAvailability) yield return ARSession.CheckAvailability();
            if (ARSession.state == ARSessionState.NeedsInstall) yield return ARSession.Install();
            if (ARSession.state == ARSessionState.Unsupported || ARSession.state == ARSessionState.NeedsInstall)
            { arUnsupported = true; statusKey = "noAR"; Go(State.Home); statusKey = "noAR"; yield break; }
            session.enabled = true; arReady = true;
            Go(State.ScanSearch);
        }

        ARTrackedImage Sheet()
        {
            if (!trackedImages) return null;
            foreach (var t in trackedImages.trackables) if (t.trackingState == TrackingState.Tracking) return t;
            return null;
        }

        void Update()
        {
            float dt = Time.deltaTime; stateT += dt;
            TickAudio(dt);
            if (paused) return;
            switch (state)
            {
                case State.ScanSearch:
                    if (Sheet()) Go(State.ScanLocked);
                    else if (stateT > HelpAfter) Go(State.ScanHelp);
                    break;
                case State.ScanLocked:
                    if (!Sheet()) { lockedFor = 0; Go(State.ScanSearch); break; }
                    lockedFor += dt;
                    if (lockedFor >= LockSeconds && !capturing) StartCoroutine(Capture(Sheet()));
                    break;
                case State.ScanHelp:
                    if (Sheet()) Go(State.ScanLocked);
                    break;
                case State.Reveal:
                    if (stateT >= RevealSeconds) Go(State.LiveIdle);
                    break;
                case State.LiveIdle:
                    if (TrackingLost()) { untracked += dt; if (untracked > LostAfter) Go(State.LiveLost); } else untracked = 0;
                    if (Time.time - idleSince > GreetAfter && greetCount < GreetMax && Time.time - lastGreet > GreetEvery && !voice.isPlaying) Greet();
                    var tap = TapOutsideUI();
                    if (tap.HasValue)
                    {   // the angel is the button (screen 06): tap the 3D title = read it, anywhere else = trumpet
                        lastTouch = Time.time; moreOpen = false;
                        if (OnTitle(tap.Value)) { Cue(cueClick); StartCoroutine(ReadSequence()); } else Blow();
                    }
                    break;
                case State.LiveBlow:
                    if (stateT >= BlowSeconds) Go(State.LiveIdle);
                    break;
                case State.LiveGreet:
                    if (!voice.isPlaying && stateT > 0.5f) Go(State.LiveIdle);
                    break;
                case State.LiveLost:
                    if (!TrackingLost()) { untracked = 0; statusKey = "tap"; Go(State.LiveIdle); }
                    break;
            }
            if (Input.GetKeyDown(KeyCode.Escape)) Back();   // Android back button
        }

        bool TrackingLost() => !showMode && anchoredSheet && anchoredSheet.trackingState != TrackingState.Tracking;

        void Back()
        {
            if (state >= State.LiveIdle) Rescan();
            else if (state >= State.ScanSearch && state != State.Reveal) Go(State.Home);
            else if (state == State.Home) Application.Quit();
        }

        void Rescan()
        {
            StopVoice(); greetCount = 0; moreOpen = false;
            if (arReady) Go(State.ScanSearch); else Go(State.Home);
        }

        // ---------------- capture / bake ----------------
        IEnumerator Capture(ARTrackedImage sheet)
        {
            capturing = true;
            yield return new WaitForEndOfFrame();
            int W = Screen.width, H = Screen.height;
            var rt = RenderTexture.GetTemporary(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            Graphics.Blit(null, rt, cameraBackground.material);
            var frameTex = new Texture2D(W, H, TextureFormat.RGBA32, false);
            var prev = RenderTexture.active; RenderTexture.active = rt;
            frameTex.ReadPixels(new Rect(0, 0, W, H), 0, 0, false);
            RenderTexture.active = prev; RenderTexture.ReleaseTemporary(rt);
            var frame = frameTex.GetPixels32(); Destroy(frameTex);

            var expected = new Vector2[4];
            for (int i = 0; i < 4; i++) { var s = arCamera.WorldToScreenPoint(sheet.transform.TransformPoint(PageToLocal(sheet, tpl.markers[i]))); expected[i] = new Vector2(s.x, s.y); }
            float markerPx = Vector2.Distance(expected[0], expected[1]) / Mathf.Max(1, tpl.markers[1].x - tpl.markers[0].x) * 64;
            float radius = Mathf.Max(16, markerPx * 1.5f);
            var pts = PageWarp.RefineMarkers(frame, W, H, expected, radius);
            if (pts == null)
            {
                var flipped = new Vector2[4];
                for (int i = 0; i < 4; i++) flipped[i] = new Vector2(expected[i].x, H - 1 - expected[i].y);
                var f = PageWarp.RefineMarkers(frame, W, H, flipped, radius);
                if (f != null) { for (int i = 0; i < 4; i++) f[i].y = H - 1 - f[i].y; FlipRows(frame, W, H); pts = f; }
            }
            bool refined = pts != null; if (!refined) pts = expected;
            Debug.Log($"DoodLive capture {W}x{H} markers refined={refined}");
            var Hm = PageWarp.Homography(tpl.markers, pts);
            if (Hm == null) { capturing = false; lockedFor = 0; Go(State.ScanSearch); yield break; }
            rawPx = PageWarp.WarpArt(frame, W, H, Hm, tpl.art, TexSize);
            PageWarp.WhiteBalance(rawPx);
            cleanPx = PageWarp.EraseLines(rawPx, TexSize, TexSize);
            ApplyPage();
            PlaceOnSheet(sheet);
            ShowTitle(sheet.referenceImage.name);
            capturing = false;
            statusKey = "recognised";
            Go(State.Reveal);
        }

        static void FlipRows(Color32[] px, int W, int H)
        {
            var row = new Color32[W];
            for (int y = 0; y < H / 2; y++)
            {
                System.Array.Copy(px, y * W, row, 0, W); System.Array.Copy(px, (H - 1 - y) * W, px, y * W, W); System.Array.Copy(row, 0, px, (H - 1 - y) * W, W);
            }
        }

        Vector3 PageToLocal(ARTrackedImage sheet, Vector2 px)
        {
            var size = sheet.size;
            return new Vector3((px.x / tpl.page.x - 0.5f) * size.x, 0, (0.5f - px.y / tpl.page.y) * size.y);
        }

        // ---------------- placement (LESSONS L14, L24, L25) ----------------
        ARTrackedImage anchoredSheet;
        Vector2 placePage; float placeFlat, placeYaw;

        void PlaceOnSheet(ARTrackedImage sheet)
        {
            var st = sheet.transform;
            placeFlat = Mathf.InverseLerp(0.45f, 0.85f, Mathf.Abs(Vector3.Dot(st.up, Vector3.up)));
            placePage = new Vector2(tpl.art.x + tpl.art.width / 2, tpl.art.y + tpl.art.height / 2);
            var pos = st.TransformPoint(PageToLocal(sheet, placePage));
            var toViewer = Vector3.ProjectOnPlane(arCamera.transform.position - pos, Vector3.up);
            if (toViewer.sqrMagnitude < 1e-4f) toViewer = Vector3.ProjectOnPlane(-st.forward, Vector3.up);
            placeYaw = Quaternion.LookRotation(toViewer.normalized, Vector3.up).eulerAngles.y;
            var oldAnchor = holder.parent && holder.parent.GetComponent<ARAnchor>() ? holder.parent.gameObject : null;
            holder.SetParent(st, false);
            if (oldAnchor) Destroy(oldAnchor);
            anchoredSheet = sheet;
            FitToSheet(1f);
        }

        void FitToSheet(float k)
        {
            var sheet = anchoredSheet; if (!sheet) return;
            var st = sheet.transform;
            var pos = st.TransformPoint(PageToLocal(sheet, placePage)) + st.up * (0.03f * (1 - placeFlat) * sheet.size.x);
            float scale = tpl.art.width / tpl.page.x * sheet.size.x * Mathf.Lerp(1f, scaleOnSheet, placeFlat);
            holder.position = Vector3.Lerp(holder.position, pos, k);
            holder.rotation = Quaternion.Euler(0, placeYaw, 0);
            var ls = holder.parent ? holder.parent.lossyScale : Vector3.one;
            holder.localScale = Vector3.Lerp(holder.localScale, Vector3.one * scale / Mathf.Max(1e-4f, ls.x), k);
        }

        void LateUpdate()
        {
            if (state >= State.LiveIdle && !showMode && anchoredSheet && anchoredSheet.trackingState == TrackingState.Tracking)
                FitToSheet(Mathf.Clamp01(Time.deltaTime * 8f));
        }

        void AnchorHere()
        {
            if (!arReady) { holder.SetParent(null, true); return; }
            var go = new GameObject("AngelAnchor");
            go.transform.SetPositionAndRotation(holder.position, holder.rotation); go.AddComponent<ARAnchor>();
            var old = holder.parent; holder.SetParent(go.transform, true);
            if (old && old.GetComponent<ARAnchor>()) Destroy(old.gameObject);
            anchoredSheet = null;
        }

        void OnEnable() { if (trackedImages) trackedImages.trackedImagesChanged += OnImagesChanged; }
        void OnDisable() { if (trackedImages) trackedImages.trackedImagesChanged -= OnImagesChanged; }
        void OnImagesChanged(ARTrackedImagesChangedEventArgs e) { if (anchoredSheet && e.removed.Contains(anchoredSheet)) AnchorHere(); }

        void PlaceInFront()
        {
            var cam = arCamera.transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up); if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward; fwd.Normalize();
            holder.SetParent(null, false);
            holder.position = cam.position + cam.forward * 1.0f - Vector3.up * 0.1f;
            holder.rotation = Quaternion.LookRotation(-fwd, Vector3.up);
            holder.localScale = Vector3.one * 0.3f;
            AnchorHere();
        }

        void ApplyPage()
        {
            if (rawPx == null) return;
            pageTex.SetPixels32(showLines ? rawPx : cleanPx); pageTex.Apply(false);
            foreach (var m in pageMaterials) m.SetTexture("_BaseMap", pageTex);
        }
        void UseDemoTexture() { rawPx = cleanPx = null; foreach (var m in pageMaterials) m.SetTexture("_BaseMap", demoTexture); }

        // ---------------- titles ----------------
        string titleKey = "angel";
        bool pinyinMode { get => PlayerPrefs.GetInt("titlePinyin", 1) == 1; set => PlayerPrefs.SetInt("titlePinyin", value ? 1 : 0); }
        Transform Titles => angel.transform.Find("titles");
        void ShowTitle(string sheetName)
        {
            if (sheetName != null) { titleKey = "angel"; foreach (var k in new[] { "fiery", "wrath", "holy" }) if (sheetName.StartsWith(k)) titleKey = k; }
            var titles = Titles; if (!titles) return;
            foreach (Transform t in titles)
            {
                t.gameObject.SetActive(t.name == titleKey || t.name.StartsWith("holder_") || t.name.StartsWith(titleKey + "_"));
                foreach (Transform part in t.GetComponentsInChildren<Transform>(true))
                {
                    if (part.name == "english") part.gameObject.SetActive(!pinyinMode);
                    if (part.name == "pinyin") part.gameObject.SetActive(pinyinMode);
                }
            }
        }

        // ---------------- flow actions ----------------
        void StartReveal()
        {
            angel.gameObject.SetActive(true);
            angel.Play("Enter", 0, 0);
            sfx.PlayOneShot(chime);
            if (swell) sfx.PlayOneShot(swell, 0.8f);
            if (music && !music.isPlaying) { music.volume = musicBed; music.Play(); }
            PlayVoice(Hello, 0.9f, "hello");
            greetCount = 0; moreOpen = false; flashT = Time.time; lastTouch = Time.time + 1.5f;
            statusKey = "tap";
        }

        void Blow()
        {
            if (state != State.LiveIdle) return;
            Cue(cueClick);
            Go(State.LiveBlow);
            angel.SetTrigger(BlowId);
            sfx.PlayOneShot(fanfare);
            var L = Lines; if (L != null && L.Length > 0) { int i = lineIdx++ % L.Length; PlayVoice(L[i], fanfare.length * 0.95f, "line" + i); }
            idleSince = Time.time;
        }

        void Greet()
        {
            var G = Greets; if (G == null || G.Length == 0) { idleSince = Time.time; return; }
            Go(State.LiveGreet);
            greetCount++; lastGreet = Time.time; idleSince = Time.time;
            int g = greetIdx++ % G.Length; PlayVoice(G[g], 0, "greet" + g);
            titleBounce = Time.time;
        }

        IEnumerator ReadSequence()
        {
            // 汉字 → 拼音 → 英文: each part of the 3D title grows for a beat with a chime (voice comes in M3)
            Go(State.LiveRead);
            var titles = Titles;
            string[] order = { "hanzi", pinyinMode ? "pinyin" : "english", pinyinMode ? "english" : "pinyin" };
            string[] keys = { "readHanzi", pinyinMode ? "readPinyin" : "readEnglish", pinyinMode ? "readEnglish" : "readPinyin" };
            for (int i = 0; i < order.Length && titles; i++)
            {
                statusKey = keys[i]; readKey = keys[i]; sfx.PlayOneShot(chime, 0.5f);
                var part = FindPart(titles, order[i]);
                bool wasActive = part && part.gameObject.activeSelf;
                if (part) { part.gameObject.SetActive(true); StartCoroutine(Punch(part, ReadStep)); }
                yield return new WaitForSeconds(ReadStep);
                if (part && !wasActive) part.gameObject.SetActive(false);
            }
            statusKey = "tap"; readKey = null; idleSince = Time.time; lastTouch = Time.time;
            Go(State.LiveIdle);
        }
        string readKey;
        Transform FindPart(Transform titles, string name)
        {
            foreach (Transform t in titles) if (t.gameObject.activeSelf) foreach (var p in t.GetComponentsInChildren<Transform>(true)) if (p.name == name) return p;
            return null;
        }
        IEnumerator Punch(Transform t, float secs)
        {
            var s0 = t.localScale; float t0 = Time.time;
            while (Time.time - t0 < secs) { float k = (Time.time - t0) / secs; t.localScale = s0 * (1 + 0.18f * Mathf.Sin(Mathf.PI * Mathf.Clamp01(k * 1.25f))); yield return null; }
            t.localScale = s0;
        }

        void ShowDemo()
        {
            Cue(cueClick);
            showMode = true;
            if (!arReady)
            {   // no AR session: stop the pose driver (it would snap the camera back to the origin), sky backdrop, fixed camera
                var tpd = arCamera.GetComponent<UnityEngine.InputSystem.XR.TrackedPoseDriver>(); if (tpd) tpd.enabled = false;
                if (cameraBackground) cameraBackground.enabled = false;
                arCamera.clearFlags = CameraClearFlags.SolidColor; arCamera.backgroundColor = new Color32(0x9C, 0x6B, 0x45, 0xFF);   // warm table (Paper & Crayon mocks)
                arCamera.transform.SetPositionAndRotation(new Vector3(0, 1.2f, 0), Quaternion.identity);
            }
            UseDemoTexture(); PlaceInFront(); ShowTitle("angel");
            Go(State.Reveal);
        }

        public void Action() => Blow();

        // ---------------- audio director: voice > sfx > music, voices never overlap ----------------
        AudioSource voiceOld; float voiceFade;
        AudioClip cueClick, cueLock, cueLost;
        string voiceKey; float voiceFrom;   // what she is saying, for the speech bubble
        void PlayVoice(AudioClip clip, float delay, string key = null)
        {
            if (!clip) return;
            voiceKey = key; voiceFrom = Time.time + delay;
            if (voice.isPlaying)
            {   // hand the playing line to a fading source (150 ms) so the new one never overlaps it
                if (!voiceOld) { voiceOld = gameObject.AddComponent<AudioSource>(); voiceOld.playOnAwake = false; }
                voiceOld.clip = voice.clip; voiceOld.time = Mathf.Min(voice.time, Mathf.Max(0, voice.clip.length - 0.01f)); voiceOld.volume = voice.volume; voiceOld.Play(); voiceFade = 0.15f;
                voice.Stop();
            }
            voice.clip = clip; voice.volume = 1f;
            if (delay > 0) voice.PlayDelayed(delay); else voice.Play();
        }
        void StopVoice() { voice.Stop(); if (voiceOld) voiceOld.Stop(); }
        void TickAudio(float dt)
        {
            if (voiceOld && voiceOld.isPlaying) { voiceFade -= dt; voiceOld.volume = Mathf.Clamp01(voiceFade / 0.15f); if (voiceFade <= 0) voiceOld.Stop(); }
            if (music && music.isPlaying)
            {
                float target = paused ? 0 : (voice.isPlaying ? musicBed * 0.4f : musicBed);
                music.volume = Mathf.MoveTowards(music.volume, target, dt * (paused ? 0.8f : 0.4f));
            }
        }
        void Cue(AudioClip c) { if (c && sfx) sfx.PlayOneShot(c, 0.7f); }
        void MakeCues()
        {   // tiny synthesised UI sounds: click (wood tick), lock (bright ding), lost (low tock)
            cueClick = Tone("click", 0.045f, 1400, 0.9f, 60f);
            cueLock = Tone("lock", 0.28f, 1568, 0.6f, 9f);
            cueLost = Tone("lost", 0.16f, 220, 0.7f, 14f);
        }
        static AudioClip Tone(string name, float secs, float hz, float amp, float decay)
        {
            int sr = 44100, n = Mathf.RoundToInt(secs * sr); var d = new float[n];
            for (int i = 0; i < n; i++) { float t = i / (float)sr; d[i] = amp * Mathf.Exp(-decay * t) * Mathf.Sin(2 * Mathf.PI * hz * t) * Mathf.Min(1, i / 60f); }
            var c = AudioClip.Create(name, n, 1, sr, false); c.SetData(d, 0); return c;
        }
        void OnApplicationPause(bool p)
        {
            paused = p;
            if (p) { if (voice.isPlaying) voice.Pause(); } else { voice.UnPause(); idleSince = Time.time; }
        }

        // UI lives in ARColoringController.UI.cs (Paper & Crayon, docs/DESIGN-DIRECTION.md)
    }
}
