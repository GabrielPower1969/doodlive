// A live 3D face for one DGActor (story packs; pilot: Joseph, pipeline/js_characters.py "3D eyes"). Data-driven by
// the per-actor face3d_<id>.json the pipeline exports (copied by StorySetup to Stories/<id>/Data/):
//   controls     named 0..1 inputs; each drives blend shapes of that name on every SkinnedMeshRenderer that has them,
//                a control range mapped onto each shape (two halves of a blink = an in-between, so a half-closed lid
//                stays on the eyeball's sphere)
//   expressions  face names of faces.json (the per-clip face the timeline already uses) -> control weights + a gaze
//                offset; a new face blends in over blendSec instead of a hard swap
//   gaze         the eyes (bones eyeL / eyeR) look at the actor's current `face` target (another actor's eyes, the
//                camera for "viewer", a set node), clamped to natural angles, with small saccades every 1-3 s;
//                the lids follow the gaze a little
//   blink        random intervals (sometimes double), a blink on big gaze shifts; the clip's own `eyelids` bone
//                (the old lid cage's scale, still keyed by every clip) counts as a lid closure, so held eyes-closed
//                beats in clips keep working
//   speech       while the actor's voice plays, the brows lift with the loudness (the jaw is StoryDirector.LipSync's)
// An actor without this component behaves exactly as before. Called once per Step by StoryDirector after the clip
// pose (DGActor.Evaluate), so it only adds rotations / weights on top of the clip.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    public class DGFace3D : MonoBehaviour
    {
        [Tooltip("face3d_<id>.json exported by the pipeline (StorySetup assigns it)")]
        public TextAsset data;

        // ---------------- JSON (JsonUtility shapes) ----------------
        [Serializable] public class Shape { public string shape; public float from, to = 1; }
        [Serializable] public class Control { public string name; public Shape[] shapes; }
        [Serializable] public class W { public string c; public float w; }
        [Serializable] public class Expr { public string name; public float gazeYaw, gazePitch; public W[] weights; }
        [Serializable] public class Gaze
        {
            public float yawMax = 24, pitchUp = 13, pitchDown = 16, saccadeYaw = 2.2f, saccadePitch = 1.3f,
                saccadeMin = 0.9f, saccadeMax = 2.8f, smooth = 0.05f, lidFollowDown = 0.3f, lidFollowUp = 0.3f;
            public string lidFollowUpControl = "lidsWide";   // looking up opens the lids a little (looking down: the blink controls)
        }
        [Serializable] public class Blink
        {
            public string left = "blinkL", right = "blinkR", lidBone = "eyelids";
            public float minGap = 2.2f, maxGap = 5.5f, closeSec = 0.07f, openSec = 0.13f, doubleChance = 0.15f,
                onGazeShift = 15f, lidOpen = 1f, lidClosed = 12.78f;
        }
        [Serializable] public class Cfg
        {
            public string id, defaultFace, headBone = "head";
            public float blendSec = 0.25f, talkBrow = 0.3f;
            public string[] eyeBones, eyeMeshes, lineMeshes, suppressByBlink, talkBrowControls;
            public Gaze gaze; public Blink blink;
            public Control[] controls; public Expr[] expressions;
        }

        public Cfg Config { get; private set; }
        public bool Ready { get; private set; }

        /// <summary>Speech loudness 0..1 of this actor's voice (StoryDirector sets it every step).</summary>
        [NonSerialized] public float speak;

        struct Target { public SkinnedMeshRenderer smr; public int index; public float from, to; public float last, full; }
        DGActor actor;
        Transform head, eyeL, eyeR, lidBone;
        Vector3 fwdInHead, upInHead, fwdInEyeL, fwdInEyeR;
        string[] names;                                       // control names, index = control id
        readonly Dictionary<string, int> cid = new Dictionary<string, int>();
        List<Target>[] targets;
        float[] cur, want, outv;                              // blended control weights, expression targets, output
        bool[] suppress, talkBrow;
        int iBlinkL = -1, iBlinkR = -1, iLidsUp = -1;
        readonly Dictionary<string, Expr> expr = new Dictionary<string, Expr>();
        string pending;
        float gazeYawWant, gazePitchWant, gazeYawOff, gazePitchOff;   // expression gaze offset (blended)
        float yaw, pitch, lastYaw, lastPitch;                          // current eye angles (deg)
        float sacYaw, sacPitch, nextSaccade, t;
        float blinkT = -1, nextBlink, lastBlink = -10; bool doubleQueued;
        System.Random rnd;

        // ---------------- setup ----------------
        /// <summary>Parse the data and bind bones / blend shapes. Call while the model is in its rest pose (before
        /// the first clip evaluation): the eyes' forward is measured against the actor's facing then.</summary>
        public void Init(DGActor a)
        {
            if (Ready) return;
            actor = a;
            if (!data) { Debug.LogWarning($"DGFace3D on {name}: no data"); return; }
            try { Config = JsonUtility.FromJson<Cfg>(data.text); }
            catch (Exception e) { Debug.LogError($"DGFace3D {name}: bad data: {e.Message}"); return; }
            var c = Config;
            if (c == null || c.controls == null) { Debug.LogError($"DGFace3D {name}: no controls"); return; }
            c.gaze ??= new Gaze(); c.blink ??= new Blink();
            head = a.Bone(string.IsNullOrEmpty(c.headBone) ? "head" : c.headBone);
            if (c.eyeBones != null && c.eyeBones.Length >= 2) { eyeL = a.Bone(c.eyeBones[0]); eyeR = a.Bone(c.eyeBones[1]); }
            lidBone = a.Bone(c.blink.lidBone);
            var root = a.transform;
            if (head) { fwdInHead = head.InverseTransformDirection(root.forward); upInHead = head.InverseTransformDirection(root.up); }
            if (eyeL) fwdInEyeL = eyeL.InverseTransformDirection(root.forward);
            if (eyeR) fwdInEyeR = eyeR.InverseTransformDirection(root.forward);

            int n = c.controls.Length;
            names = new string[n]; targets = new List<Target>[n]; cur = new float[n]; want = new float[n]; outv = new float[n];
            suppress = new bool[n]; talkBrow = new bool[n];
            var smrs = GetComponentsInChildren<SkinnedMeshRenderer>(true);
            int bound = 0;
            for (int i = 0; i < n; i++)
            {
                var ctl = c.controls[i]; names[i] = ctl.name; cid[ctl.name] = i; targets[i] = new List<Target>();
                if (ctl.shapes == null) continue;
                foreach (var s in ctl.shapes)
                    foreach (var r in smrs)
                    {
                        var m = r.sharedMesh; if (!m) continue;
                        int k = m.GetBlendShapeIndex(s.shape);
                        if (k < 0) continue;
                        // full weight differs by importer: glTFast adds frames at weight 1, FBX at 100
                        float full = m.GetBlendShapeFrameWeight(k, m.GetBlendShapeFrameCount(k) - 1);
                        targets[i].Add(new Target { smr = r, index = k, from = s.from, to = s.to, last = -1, full = full > 0 ? full : 1 });
                        bound++;
                    }
            }
            iBlinkL = Id(c.blink.left); iBlinkR = Id(c.blink.right); iLidsUp = Id(c.gaze.lidFollowUpControl);
            if (c.suppressByBlink != null) foreach (var s in c.suppressByBlink) { int i = Id(s); if (i >= 0) suppress[i] = true; }
            if (c.talkBrowControls != null) foreach (var s in c.talkBrowControls) { int i = Id(s); if (i >= 0) talkBrow[i] = true; }
            if (c.expressions != null) foreach (var e in c.expressions) if (!string.IsNullOrEmpty(e.name)) expr[e.name] = e;
            rnd = new System.Random(StableSeed(a.id));
            nextBlink = Range(0.6f, c.blink.maxGap); nextSaccade = Range(c.gaze.saccadeMin, c.gaze.saccadeMax);
            Ready = true;
            if (bound == 0) Debug.LogWarning($"DGFace3D {name}: no blend shape of the data found on the model");
            SetExpression(pending ?? c.defaultFace, true);
        }

        int Id(string control) => control != null && cid.TryGetValue(control, out var i) ? i : -1;
        float Range(float a, float b) => a + (float)rnd.NextDouble() * (b - a);
        static int StableSeed(string s) { int h = 17; if (s != null) foreach (var ch in s) h = h * 31 + ch; return h; }

        /// <summary>Restart the procedural state (a story replay): eyes ahead, no blink in progress.</summary>
        public void ResetState()
        {
            if (!Ready) return;
            t = 0; blinkT = -1; lastBlink = -10; doubleQueued = false; sacYaw = sacPitch = 0;
            yaw = pitch = lastYaw = lastPitch = 0;
            nextBlink = Range(0.6f, Config.blink.maxGap); nextSaccade = Range(Config.gaze.saccadeMin, Config.gaze.saccadeMax);
            SetExpression(Config.defaultFace, true);
        }

        /// <summary>Gaze yaw is + toward the character's right, pitch + up (degrees, head frame).</summary>
        public float GazeYaw => yaw;
        public float GazePitch => pitch;

        /// <summary>Blend toward the face of this name (faces.json); unknown names fall back to the default face.</summary>
        public void SetExpression(string face, bool instant = false)
        {
            if (!Ready) { pending = face; return; }
            if (string.IsNullOrEmpty(face) || !expr.TryGetValue(face, out var e))
                if (!expr.TryGetValue(Config.defaultFace ?? "", out e)) e = null;
            Array.Clear(want, 0, want.Length);
            gazeYawWant = gazePitchWant = 0;
            if (e != null)
            {
                gazeYawWant = e.gazeYaw; gazePitchWant = e.gazePitch;
                if (e.weights != null) foreach (var w in e.weights) { int i = Id(w.c); if (i >= 0) want[i] = Mathf.Clamp01(w.w); }
            }
            if (instant) { Array.Copy(want, cur, want.Length); gazeYawOff = gazeYawWant; gazePitchOff = gazePitchWant; }
        }

        // ---------------- per step ----------------
        /// <summary>Advance by dt (0 = paused: the pose is re-applied unchanged) and pose eyes / blend shapes on top of
        /// the clip. lookAt = world point the actor attends to (null = straight ahead).</summary>
        public void Tick(float dt, Vector3? lookAt)
        {
            if (!Ready) return;
            var c = Config; var g = c.gaze; var b = c.blink;
            t += dt;
            // expression blend (about 95 % after blendSec)
            float k = dt > 0 ? 1 - Mathf.Exp(-dt * 3f / Mathf.Max(0.01f, c.blendSec)) : 0;
            for (int i = 0; i < cur.Length; i++) cur[i] += (want[i] - cur[i]) * k;
            gazeYawOff += (gazeYawWant - gazeYawOff) * k; gazePitchOff += (gazePitchWant - gazePitchOff) * k;

            // gaze: target direction in the head's frame, clamped, plus saccades
            float tyaw = 0, tpitch = 0;
            Vector3 F = Vector3.forward, U = Vector3.up, R = Vector3.right;
            if (head)
            {
                F = head.TransformDirection(fwdInHead).normalized; U = head.TransformDirection(upInHead).normalized;
                U = (U - F * Vector3.Dot(U, F)).normalized; R = Vector3.Cross(U, F);
            }
            if (eyeL && eyeR && lookAt.HasValue)
            {
                var mid = (eyeL.position + eyeR.position) * 0.5f;
                var d = lookAt.Value - mid;
                if (d.sqrMagnitude > 1e-10f)
                {
                    d.Normalize();
                    float fz = Vector3.Dot(d, F);
                    if (fz > -0.2f)                                   // a target behind the head: keep looking ahead
                    {
                        tyaw = Mathf.Atan2(Vector3.Dot(d, R), fz) * Mathf.Rad2Deg;
                        tpitch = Mathf.Asin(Mathf.Clamp(Vector3.Dot(d, U), -1, 1)) * Mathf.Rad2Deg;
                    }
                }
            }
            if (dt > 0 && t >= nextSaccade)
            {
                sacYaw = Range(-g.saccadeYaw, g.saccadeYaw); sacPitch = Range(-g.saccadePitch, g.saccadePitch);
                nextSaccade = t + Range(g.saccadeMin, g.saccadeMax);
            }
            tyaw = Mathf.Clamp(tyaw + gazeYawOff + sacYaw, -g.yawMax, g.yawMax);
            tpitch = Mathf.Clamp(tpitch + gazePitchOff + sacPitch, -g.pitchDown, g.pitchUp);
            float ks = dt > 0 ? 1 - Mathf.Exp(-dt / Mathf.Max(0.005f, g.smooth)) : 0;
            yaw += (tyaw - yaw) * ks; pitch += (tpitch - pitch) * ks;
            // a big gaze shift brings a blink (as people do)
            float shift = Mathf.Abs(tyaw - lastYaw) + Mathf.Abs(tpitch - lastPitch);
            lastYaw = tyaw; lastPitch = tpitch;
            if (dt > 0 && shift > b.onGazeShift && blinkT < 0 && t - lastBlink > 0.5f) StartBlink();

            // blinks
            if (dt > 0)
            {
                if (blinkT < 0 && t >= nextBlink) StartBlink();
                if (blinkT >= 0)
                {
                    blinkT += dt;
                    if (blinkT > b.closeSec + 0.02f + b.openSec)
                    {
                        blinkT = -1; lastBlink = t;
                        if (doubleQueued) { doubleQueued = false; nextBlink = t + 0.12f; }
                        else nextBlink = t + Range(b.minGap, b.maxGap);
                    }
                }
            }
            float blink = 0;
            if (blinkT >= 0)
            {
                if (blinkT < b.closeSec) { float u = blinkT / b.closeSec; blink = u * u; }
                else if (blinkT < b.closeSec + 0.02f) blink = 1;
                else { float u = (blinkT - b.closeSec - 0.02f) / Mathf.Max(0.01f, b.openSec); blink = 1 - u * u * (3 - 2 * u); }
            }
            if (lidBone)                                              // the clip's eyes-closed beats (old lid cage scale)
            {
                var s = lidBone.localScale;
                float sy = Mathf.Max(s.x, Mathf.Max(s.y, s.z));
                blink = Mathf.Max(blink, Mathf.InverseLerp(b.lidOpen, b.lidClosed, sy));
            }
            float follow = pitch < 0 ? -pitch / Mathf.Max(1, g.pitchDown) * g.lidFollowDown : 0;   // looking down: lids lower

            // pose the eyes on top of the clip (the clip keys them at rest)
            if (eyeL && eyeR)
            {
                float yr = yaw * Mathf.Deg2Rad, pr = pitch * Mathf.Deg2Rad;
                var dw = F * (Mathf.Cos(pr) * Mathf.Cos(yr)) + R * (Mathf.Cos(pr) * Mathf.Sin(yr)) + U * Mathf.Sin(pr);
                Aim(eyeL, fwdInEyeL, dw); Aim(eyeR, fwdInEyeR, dw);
            }

            // final control values -> blend shapes
            float blinkMax = 0;
            for (int i = 0; i < cur.Length; i++)
            {
                float v = cur[i];
                if (i == iBlinkL || i == iBlinkR) { v = Mathf.Max(Mathf.Max(v, blink), Mathf.Min(1, v + follow)); blinkMax = Mathf.Max(blinkMax, v); }
                outv[i] = v;
            }
            float up = pitch > 0 ? pitch / Mathf.Max(1, g.pitchUp) * g.lidFollowUp : 0;
            for (int i = 0; i < cur.Length; i++)
            {
                float v = outv[i];
                if (suppress[i]) v *= 1 - blinkMax;
                if (talkBrow[i]) v = Mathf.Min(1, v + c.talkBrow * Mathf.Clamp01(speak));
                if (i == iLidsUp) v = Mathf.Min(1, v + up * (1 - blinkMax));
                Apply(i, Mathf.Clamp01(v));
            }
        }

        void StartBlink()
        {
            blinkT = 0;
            doubleQueued = !doubleQueued && rnd.NextDouble() < Config.blink.doubleChance;
        }

        static void Aim(Transform eye, Vector3 fwdLocal, Vector3 dirWorld)
        {
            var cur = eye.TransformDirection(fwdLocal);
            eye.rotation = Quaternion.FromToRotation(cur, dirWorld) * eye.rotation;
        }

        void Apply(int i, float v)
        {
            var list = targets[i];
            for (int j = 0; j < list.Count; j++)
            {
                var tg = list[j];
                float w = Mathf.Clamp01((v - tg.from) / Mathf.Max(1e-4f, tg.to - tg.from)) * tg.full;
                if (Mathf.Abs(w - tg.last) < 0.0005f * tg.full || !tg.smr) continue;
                tg.smr.SetBlendShapeWeight(tg.index, w);
                tg.last = w; list[j] = tg;
            }
        }

        /// <summary>World point between the eyes (others look here when this actor is their target).</summary>
        public Vector3? EyeCenter => eyeL && eyeR ? (eyeL.position + eyeR.position) * 0.5f : (Vector3?)null;
    }
}
