// Where the stage (the angel or a story) stands in the room, and how the child looks at it (docs/ANCHORING-DESIGN.md).
//
//   StageRoot (ARAnchor, world pose: position + yaw about gravity)  ->  Holder (local: user yaw, base x user scale)
//
// - The stage is anchored in the room, never parented to the sheet. Seeing the sheet only *refines* the anchor, so the
//   play keeps running when the sheet leaves the picture (moving close, looking from the side). Only the app going to
//   the background holds a story.
// - Refining is filtered: a new anchor is made only when several sheet sightings agree with each other and differ from
//   the stage by more than a dead band. Single bad reads (a marker half out of view) and pose noise do not move it,
//   so the stage does not creep or shake.
// - Reparenting keeps the world pose and the Holder eases its local pose to the new target: every move is a glide.
// - Two fingers: pinch = size (0.5x..4x), twist = turn. The reset chip brings both back.
// - Off screen for a moment: an arrow at the edge points to the stage; a little later a button brings it in front of
//   the phone (onto the table when a plane is found).
// - Demo (a book from the shelf): the stage appears in front of the phone and settles onto the table when ARCore finds
//   it. Film mode (no AR) stays as the fallback and as a grown-ups option.
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;

namespace DoodLive
{
    public partial class ARColoringController
    {
        enum StageMode { None, Sheet, Front, Surface, Film }
        StageMode stageMode = StageMode.None;
        Transform stageRoot;
        float baseScale = 0.3f, userScale = 1f, userYaw;
        Vector3 baseOffset;                     // holder local offset under the root (upright-sheet lift)

        // ---------------- roots ----------------
        void MoveStage(Vector3 pos, float yaw, float scale, bool glide = true)
        {
            var go = new GameObject("StageAnchor");
            go.transform.SetPositionAndRotation(pos, Quaternion.Euler(0, yaw, 0));
            if (arReady && ARSession.state == ARSessionState.SessionTracking) go.AddComponent<ARAnchor>();
            var old = stageRoot;
            stageRoot = go.transform;
            baseScale = scale;
            foreach (var h in new[] { holder, dgHolder })
            {
                if (!h) continue;
                if (h == Holder) { h.SetParent(stageRoot, glide); if (!glide) SnapHolder(); }
                else if (old && h.parent == old) h.SetParent(null, true);
            }
            if (old) Destroy(old.gameObject);
            stageMoves++;
            var am = FindAnyObjectByType<ARAnchorManager>();
            Debug.Log($"DoodLive stage {stageMode} #{stageMoves} at {pos.x:0.000},{pos.y:0.000},{pos.z:0.000} yaw {yaw:0} scale {scale:0.000} anchors {(am ? am.trackables.count : -1)}");
        }
        int stageMoves;

        void SnapHolder()
        {
            var h = Holder; if (!h || h.parent != stageRoot) return;
            h.localPosition = baseOffset; h.localRotation = Quaternion.Euler(0, userYaw, 0); h.localScale = Vector3.one * baseScale * userScale;
        }

        /// <summary>Both holders out of any root (before a root or a finder anchor is destroyed), stage forgotten.</summary>
        void DetachStage()
        {
            if (holder) holder.SetParent(null, true);
            if (dgHolder) dgHolder.SetParent(null, true);
            if (stageRoot) Destroy(stageRoot.gameObject);
            stageRoot = null; stageMode = StageMode.None; anchoredSheet = null; samples.Clear();
            userScale = 1; userYaw = 0; baseOffset = Vector3.zero;
            offscreenFor = 0; settling = false;
        }

        // ---------------- on the sheet ----------------
        float sheetHeading0;   // the sheet's heading when the stage was placed (turning the paper turns the stage)
        bool placeOnFlat;

        static float Heading(Vector3 v) { v = Vector3.ProjectOnPlane(v, Vector3.up); return v.sqrMagnitude < 1e-6f ? 0 : Quaternion.LookRotation(v.normalized, Vector3.up).eulerAngles.y; }
        float SheetHeading(Transform st) => Heading(placeOnFlat ? st.forward : st.up);

        /// <summary>Stage pose the sheet asks for now (same rules as the original FitToSheet).</summary>
        void SheetStagePose(SheetTarget sheet, out Vector3 pos, out float yaw, out float scale)
        {
            var st = sheet.transform;
            pos = st.TransformPoint(PageToLocal(sheet, placePage)) + st.up * (0.03f * (1 - placeFlat) * sheet.size.x);
            float artW = tpl.art.width / tpl.page.x * sheet.size.x;
            scale = dgMode ? artW : artW * Mathf.Lerp(1f, scaleOnSheet, placeFlat);
            yaw = placeYaw + Mathf.DeltaAngle(sheetHeading0, SheetHeading(st));
            if (dgMode) pos += Quaternion.Euler(0, yaw, 0) * Vector3.forward * (0.3f * artW * (1 - placeFlat));
        }

        struct Sample { public Vector3 pos; public float yaw, scale, t; }
        readonly List<Sample> samples = new List<Sample>();
        float lastSampleSeen = -1, lastSampleAt;

        void RefineFromSheet()
        {
            var sheet = anchoredSheet;
            if (stageMode != StageMode.Sheet || sheet == null || !sheet.IsAlive || !sheet.Tracking || !stageRoot) return;
            // one sample per new sighting (marker path: a detection; image path: at most 10 a second)
            if (sheet.Image) { if (Time.time - lastSampleAt < 0.1f) return; }
            else { if (sheet.LastSeen == lastSampleSeen) return; lastSampleSeen = sheet.LastSeen; }
            lastSampleAt = Time.time;
            SheetStagePose(sheet, out var p, out var y, out var s);
            samples.Add(new Sample { pos = p, yaw = y, scale = s, t = Time.time });
            while (samples.Count > 5 || (samples.Count > 0 && Time.time - samples[0].t > 2f)) samples.RemoveAt(0);
            if (samples.Count < 3) return;

            // robust centre: per-axis median, yaw relative to the newest sample
            var xs = new List<float>(); var ys = new List<float>(); var zs = new List<float>(); var yw = new List<float>(); var sc = new List<float>();
            float yRef = samples[samples.Count - 1].yaw;
            foreach (var q in samples) { xs.Add(q.pos.x); ys.Add(q.pos.y); zs.Add(q.pos.z); yw.Add(Mathf.DeltaAngle(yRef, q.yaw)); sc.Add(q.scale); }
            var med = new Vector3(Median(xs), Median(ys), Median(zs)); float medYaw = yRef + Median(yw), medScale = Median(sc);

            float artW = medScale, tol = Mathf.Max(0.01f, 0.06f * artW), dead = Mathf.Max(0.008f, 0.04f * artW);
            // the newest 3 must agree with each other (no single wild read moves the stage)
            for (int i = samples.Count - 3; i < samples.Count; i++)
                if (Vector3.Distance(samples[i].pos, med) > tol || Mathf.Abs(Mathf.DeltaAngle(samples[i].yaw, medYaw)) > 5f) return;
            float dPos = Vector3.Distance(med, stageRoot.position), dYaw = Mathf.Abs(Mathf.DeltaAngle(medYaw, stageRoot.eulerAngles.y));
            float dScale = Mathf.Abs(medScale / Mathf.Max(1e-4f, baseScale) - 1);
            if (dPos < dead && dYaw < 4f && dScale < 0.06f) return;   // inside the dead band: the stage stays exactly where it is
            MoveStage(med, medYaw, medScale);
            samples.Clear();
        }

        static float Median(List<float> v) { v.Sort(); int n = v.Count; return n % 2 == 1 ? v[n / 2] : (v[n / 2 - 1] + v[n / 2]) / 2; }

        // ---------------- in front / on the table ----------------
        ARRaycastManager Raycasts => finder ? finder.raycasts : null;
        static readonly List<ARRaycastHit> hits = new List<ARRaycastHit>();

        bool TableUnder(Vector3 from, out Vector3 at)
        {
            at = default; var rc = Raycasts; if (!rc) return false;
            if (!rc.Raycast(new Ray(from + Vector3.up * 0.3f, Vector3.down), hits, TrackableType.PlaneWithinPolygon)) return false;
            foreach (var hHit in hits)
                if (Vector3.Dot(hHit.pose.up, Vector3.up) > 0.9f && from.y - hHit.pose.position.y < 1.3f) { at = hHit.pose.position; return true; }
            return false;
        }

        bool TableAtScreenCentre(out Vector3 at)
        {
            at = default; var rc = Raycasts; if (!rc) return false;
            if (!rc.Raycast(new Vector2(Screen.width / 2f, Screen.height / 2f), hits, TrackableType.PlaneWithinPolygon)) return false;
            foreach (var hHit in hits)
                if (Vector3.Dot(hHit.pose.up, Vector3.up) > 0.9f && hHit.distance > 0.15f && hHit.distance < 2.2f) { at = hHit.pose.position; return true; }
            return false;
        }

        /// <summary>Stage in front of the phone, facing it; on the table at the screen centre when one is known.</summary>
        void PlaceFront(float scale)
        {
            var cam = arCamera.transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up); if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.ProjectOnPlane(cam.up, Vector3.up);
            fwd.Normalize();
            float yaw = Quaternion.LookRotation(-fwd, Vector3.up).eulerAngles.y;
            anchoredSheet = null; samples.Clear(); baseOffset = Vector3.zero;
            if (TableAtScreenCentre(out var at)) { stageMode = StageMode.Surface; MoveStage(at, yaw, scale); return; }
            // nothing found yet: along the view, 0.6 m out, never above eye level
            var pos = cam.position + cam.forward * 0.6f; pos.y = Mathf.Min(pos.y, cam.position.y - 0.15f);
            stageMode = StageMode.Front; MoveStage(pos, yaw, scale);
            if (!settling) StartCoroutine(SettleOnTable());
        }

        bool settling;
        IEnumerator SettleOnTable()
        {
            settling = true; float t0 = Time.time;
            while (settling && stageMode == StageMode.Front && stageRoot && Time.time - t0 < 15f)
            {
                yield return new WaitForSeconds(0.25f);
                if (stageMode != StageMode.Front || !stageRoot) break;
                if (TableUnder(stageRoot.position, out var at) || TableAtScreenCentre(out at))
                { stageMode = StageMode.Surface; MoveStage(at, stageRoot.eulerAngles.y, baseScale); Cue(cueLock); break; }
            }
            settling = false;
        }

        /// <summary>The AR demo: wait for tracking (at most 4 s), put the stage in front, then start.</summary>
        IEnumerator StartArStage(float scale, bool reveal)
        {
            statusKey = "openingCam";
            float t0 = Time.time;
            while (ARSession.state != ARSessionState.SessionTracking && Time.time - t0 < 4f) yield return null;
            PlaceFront(scale); SnapHolder();
            if (reveal) Go(State.Reveal);
        }

        void BringBack()
        {
            if (!arReady || !Holder) return;
            Cue(cueClick);
            PlaceFront(stageMode == StageMode.Sheet ? baseScale : Mathf.Max(baseScale, 0.2f));
            offscreenFor = 0;
        }

        // ---------------- per frame ----------------
        void StageLateUpdate()
        {
            if (stageMode == StageMode.Film || !stageRoot) return;
            // placed before ARCore was tracking (phone face down, dark room): anchor it as soon as tracking starts
            if (arReady && ARSession.state == ARSessionState.SessionTracking && !stageRoot.GetComponent<ARAnchor>())
                stageRoot.gameObject.AddComponent<ARAnchor>();
            if (state >= State.Reveal) RefineFromSheet();
            var h = Holder; if (!h || h.parent != stageRoot) return;
            float k = 1 - Mathf.Exp(-Time.deltaTime * 6f);   // ~0.35 s glide
            h.localPosition = Vector3.Lerp(h.localPosition, baseOffset, k);
            h.localRotation = Quaternion.Slerp(h.localRotation, Quaternion.Euler(0, userYaw, 0), k);
            h.localScale = Vector3.Lerp(h.localScale, Vector3.one * baseScale * userScale, k);
            TrackOffscreen();
        }

        // ---------------- gestures ----------------
        bool pinching, twisting, multiTouch; float pinchD0, pinchA0, pinchS0, pinchY0;
        void StageGestures()
        {
            if (Input.touchCount == 0) { multiTouch = false; pinching = false; return; }
            if (Input.touchCount != 2 || !arReady || stageMode == StageMode.Film || !stageRoot || state < State.Reveal || moreOpen) { pinching = false; return; }
            multiTouch = true;
            var a = Input.GetTouch(0).position; var b = Input.GetTouch(1).position;
            float d = (a - b).magnitude, ang = Mathf.Atan2(b.y - a.y, b.x - a.x) * Mathf.Rad2Deg;
            if (!pinching) { pinching = true; twisting = false; pinchD0 = Mathf.Max(1, d); pinchA0 = ang; pinchS0 = userScale; pinchY0 = userYaw; return; }
            userScale = Mathf.Clamp(pinchS0 * d / pinchD0, 0.5f, 4f);
            float turn = Mathf.DeltaAngle(pinchA0, ang);
            if (!twisting && Mathf.Abs(turn) > 10f) { twisting = true; pinchA0 = ang; pinchY0 = userYaw; turn = 0; }
            if (twisting) userYaw = pinchY0 - turn;   // fingers turn anticlockwise on screen = stage turns anticlockwise seen from above
            lastTouch = Time.time;
        }
        bool StageAdjusted => Mathf.Abs(userScale - 1) > 0.04f || Mathf.Abs(Mathf.DeltaAngle(userYaw, 0)) > 4f;

        // ---------------- off screen: find it back ----------------
        float offscreenFor, nextVisCheck; bool stageVisible = true; Vector2 stageDir;
        readonly List<Renderer> stageRenderers = new List<Renderer>();
        void TrackOffscreen()
        {
            if (!arReady || state < State.LiveIdle) { offscreenFor = 0; return; }
            if (Time.time >= nextVisCheck)
            {
                nextVisCheck = Time.time + 0.2f;
                stageVisible = StageOnScreen(out stageDir);
            }
            offscreenFor = stageVisible ? 0 : offscreenFor + Time.deltaTime;
        }

        bool StageOnScreen(out Vector2 dir)
        {
            dir = Vector2.down;
            var h = Holder; if (!h) return true;
            h.GetComponentsInChildren(false, stageRenderers);
            bool any = false; var b = new Bounds();
            foreach (var r in stageRenderers) { if (!r.enabled || r is ParticleSystemRenderer) continue; if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds); }
            if (!any) return true;
            var cam = arCamera; var cp = cam.transform.position;
            if (b.Contains(cp)) return true;
            float x0 = 1, y0 = 1, x1 = 0, y1 = 0; int front = 0;
            for (int i = 0; i < 9; i++)
            {
                var c = i == 8 ? b.center : new Vector3(i % 2 == 0 ? b.min.x : b.max.x, (i / 2) % 2 == 0 ? b.min.y : b.max.y, i / 4 == 0 ? b.min.z : b.max.z);
                var v = cam.WorldToViewportPoint(c); if (v.z <= 0) continue;
                front++; x0 = Mathf.Min(x0, v.x); x1 = Mathf.Max(x1, v.x); y0 = Mathf.Min(y0, v.y); y1 = Mathf.Max(y1, v.y);
            }
            var vc = cam.WorldToViewportPoint(b.center);
            dir = new Vector2(vc.x - 0.5f, vc.y - 0.5f); if (vc.z < 0) dir = -dir;
            if (dir.sqrMagnitude < 1e-4f) dir = Vector2.down;
            dir.Normalize();
            if (front == 0) return false;
            if (front < 9) return true;   // some corners behind the phone: the stage is around it (very close)
            return x1 > 0.02f && x0 < 0.98f && y1 > 0.02f && y0 < 0.98f;
        }

        // ---------------- UI ----------------
        void StageGUI(float w, float h, float top, float bottom, float edge, float chip)
        {
            bool live = state >= State.LiveIdle;
            // arrow at the screen edge, pointing to the stage
            float arrowA = Fade("findArrow", live && arReady && offscreenFor > 1.0f && !moreOpen, 4f);
            if (arrowA > 0)
            {
                var gd = new Vector2(stageDir.x, -stageDir.y);   // GUI y goes down
                var c = new Vector2(w / 2, h / 2);
                float mx = w / 2 - u * 1.3f, my = h / 2 - top - u * 2.2f;
                float t = Mathf.Min(Mathf.Abs(gd.x) > 1e-3f ? mx / Mathf.Abs(gd.x) : 1e9f, Mathf.Abs(gd.y) > 1e-3f ? my / Mathf.Abs(gd.y) : 1e9f);
                var p = c + gd * t;
                float pulse = 1 + 0.12f * Mathf.Sin(Time.time * 6f), s = u * 1.5f * pulse;
                GUI.color = new Color(1, 1, 1, arrowA);
                var disc = new Rect(p.x - s / 2, p.y - s / 2, s, s);
                Card(disc, boxSun, lip * 0.5f);
                var m = GUI.matrix; GUIUtility.RotateAroundPivot(Mathf.Atan2(gd.y, gd.x) * Mathf.Rad2Deg, disc.center);
                var play = Icon("play"); if (play) GUI.DrawTexture(new Rect(disc.x + s * 0.24f, disc.y + s * 0.22f, s * 0.56f, s * 0.56f), play, ScaleMode.ScaleToFit);
                GUI.matrix = m;
                // label next to the arrow, pulled towards the centre
                string txt = L10n.T("findBack"); var st = T(false);
                float lw = st.CalcSize(new GUIContent(txt)).x + u * 0.7f, lh = u * 0.9f;
                var lc = p - gd * (s * 0.5f + u * 0.4f + Mathf.Abs(gd.x) * lw * 0.5f + Mathf.Abs(gd.y) * lh * 0.5f);
                var lr = new Rect(Mathf.Clamp(lc.x - lw / 2, edge, w - edge - lw), Mathf.Clamp(lc.y - lh / 2, top + edge, h - bottom - lh - edge), lw, lh);
                Card(lr, boxPaper, lip * 0.5f); GUI.Label(lr, txt, st);
                GUI.color = Color.white;
                uiRects.Add(disc); uiRects.Add(lr);
            }
            // after a few seconds: bring it here
            float bringA = Fade("bringBack", live && arReady && offscreenFor > 4f && !moreOpen, 4f);
            if (bringA > 0)
            {
                GUI.color = new Color(1, 1, 1, bringA);
                float bw = Mathf.Min(w - edge * 4 - chip * 2, u * 6f), bh = u * 1.1f;
                var r = new Rect(w / 2 - bw / 2, h * 0.5f - bh / 2, bw, bh);
                if (PaperButton(r, L10n.T("bringBack"), boxSun, txtTag) && bringA > 0.5f) BringBack();
                uiRects.Add(r);
                GUI.color = Color.white;
            }
            // reset chip after a pinch or twist
            float resetA = Fade("stageReset", (live || state == State.Reveal) && arReady && StageAdjusted && !moreOpen, 4f);
            if (resetA > 0)
            {
                GUI.color = new Color(1, 1, 1, resetA);
                var r = new Rect(edge, h - bottom - edge - chip - lip, chip, chip);
                if (Chip(r, Icon("restart"), DesignTokens.Paper, 0.55f) && resetA > 0.5f) { Cue(cueClick); userScale = 1; userYaw = 0; }
                uiRects.Add(r);
                GUI.color = Color.white;
            }
            // tracking weak for a while: a gentle hint, the play goes on
            bool weak = arReady && live && stageMode != StageMode.Film && ARSession.state != ARSessionState.SessionTracking;
            weakFor = weak ? weakFor + Time.unscaledDeltaTime : 0;
            float weakA = Fade("weakTrack", weakFor > 1.5f, 3f);
            if (weakA > 0)
            {
                GUI.color = new Color(1, 1, 1, weakA);
                string txt = L10n.T("slowDown"); var st = T(false);
                float pw = Mathf.Min(w - chip * 2 - edge * 4, st.CalcSize(new GUIContent(txt)).x + u * 0.9f);
                float ph = st.CalcHeight(new GUIContent(txt), pw - u * 0.6f) + u * 0.35f;
                var r = new Rect(w / 2 - pw / 2, top + edge, pw, ph);
                Card(r, boxPaper, lip * 0.6f); GUI.Label(new Rect(r.x + u * 0.3f, r.y, pw - u * 0.6f, ph), txt, st);
                GUI.color = Color.white;
            }
        }
        float weakFor;

        // ---------------- film <-> AR (grown-ups panel) ----------------
        bool PreferFilm { get => PlayerPrefs.GetInt("demoFilm", 0) == 1; set { PlayerPrefs.SetInt("demoFilm", value ? 1 : 0); PlayerPrefs.Save(); } }

        void SwitchToFilm()
        {
            PreferFilm = true;
            if (!showMode || active == null && !angel.gameObject.activeSelf) return;
            if (session) session.enabled = false;
            arReady = false;
            DetachStage(); stageMode = StageMode.Film;
            NoArCamera();
            PlaceInFrontFixed();
            if (dgMode && active != null) active.Cinematic = arCamera;
        }

        void SwitchToAr()
        {
            PreferFilm = false;
            if (showMode) StartCoroutine(SwitchToArRoutine());
        }

        IEnumerator SwitchToArRoutine()
        {   // the story keeps playing while the camera comes on; the stage then appears in front and settles on the table
            yield return EnsureAr();
            if (arFail != null) { statusKey = ""; yield break; }
            if (dgMode && active != null) active.Cinematic = null;
            RestoreArCamera(false);
            session.enabled = true; arReady = true;
            yield return StartArStage(0.3f, false);
            statusKey = "";
        }

        /// <summary>Film mode placement: a fixed camera, the stage in front of it, no anchor.</summary>
        void PlaceInFrontFixed()
        {
            var cam = arCamera.transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up); if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward; fwd.Normalize();
            var h = Holder;
            h.SetParent(null, false);
            // D&G: a 0.3 m wide stage a little below eye level (the page lies flat, so it must sit lower than the angel)
            h.position = dgMode ? cam.position + fwd * 0.75f - Vector3.up * 0.3f : cam.position + cam.forward * 1.0f - Vector3.up * 0.1f;
            h.rotation = Quaternion.LookRotation(-fwd, Vector3.up);
            h.localScale = Vector3.one * 0.3f;
            stageMode = StageMode.Film;
        }
    }
}
