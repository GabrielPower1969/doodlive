// Runtime side of the Exodus effects (docs/exodus/FX.md "Wiring for Integration").
// A hidden singleton (auto-created, runs after every DGFxInstance) that, once per frame:
//   1. resets ExodusSea when DGFx.StopAll has run (StoryLight.Epoch) and advances ExodusSea.Clock while not paused;
//   2. finds the Exodus set nodes under DGFx.Stage by name (CONTRACT §6: seaWallBack, seaWallFront, seaWaterLane, plus
//      nileWater / doorMarks / seaBed for measuring) and measures their stage-local bounds into ExodusFx.Boxes and the
//      sea geometry into ExodusSea; a missing node is logged once and skipped (the sprites still play);
//   3. applies ExodusSea.Open to the set: walls shown and scaled from their flat rest (scale.y x RestScale) to full height
//      with a gentle swell while standing, seaWaterLane hidden while the lane is open;
//   4. keeps one `sea_hold` effect alive while the sea is open (foam crests, caustics), removes it at rest;
//   5. fills ExodusFx.Actors (stage-local feet + height of every DGActor under DGFx.Stage) while an effect asks.
// Fast-forward: StoryDirector.EndSeek calls ExodusStage.Seek(seekFx, t) (see FX.md); ExodusSea.SetState also works.
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    [DefaultExecutionOrder(200)]   // after DGFxInstance (0) and StoryTintStage (100): the walls follow this frame's Open
    public sealed class ExodusStage : MonoBehaviour
    {
        public const string WallBack = "seaWallBack", WallFront = "seaWallFront", Lane = "seaWaterLane";
        static readonly string[] Measured = { "nileWater", "doorMarks", "seaBed", Lane };

        static ExodusStage inst;
        Transform stage;
        int epoch = int.MinValue;
        Transform wallBack, wallFront, lane;
        bool searched, warned;
        float lastScale = -1f; int lastActive = -1, lastLane = -1;
        DGFxInstance hold;
        float actorScan;
        DGActor[] actors = new DGActor[0];
        // full-height scale of each wall, captured once per transform (so a re-scan never mistakes a raised wall for rest)
        readonly Dictionary<Transform, Vector3> fullScale = new Dictionary<Transform, Vector3>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        public static void Ensure()
        {
            if (inst) return;
            var go = new GameObject("ExodusStage") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            inst = go.AddComponent<ExodusStage>();
        }

        /// <summary>Fast-forward hook for StoryDirector.EndSeek: 'passed' = every fx cue met while seeking (seekFx), t = the
        /// seek time. Sets the sea parted when a sea_part has started and no sea_close has finished by t; does nothing when
        /// the list holds neither id (every other story). Call it after DGFx.StopAll (Begin) and before the replay loop.</summary>
        public static void Seek(IList<DGFxCue> passed, float t)
        {
            if (passed == null) return;
            float part = float.NegativeInfinity, closeEnd = float.NegativeInfinity;
            bool any = false;
            foreach (var f in passed)
            {
                if (f == null) continue;
                if (f.id == "sea_part" && f.t <= t) { any = true; part = Mathf.Max(part, f.t); }
                else if (f.id == "sea_close" && f.t <= t) { any = true; closeEnd = Mathf.Max(closeEnd, f.t + (f.dur > 0 ? f.dur : 3f)); }
            }
            if (!any) return;
            ExodusSea.SetState(part > float.NegativeInfinity && !(closeEnd > part && closeEnd <= t));
            Ensure();
        }

        void LateUpdate()
        {
            ExodusSea.Sync();
            if (!DGFx.Paused) ExodusSea.Clock += Time.deltaTime * DGFx.TimeScale;

            var st = DGFx.Stage;
            if (st != stage || epoch != StoryLight.Epoch)
            {
                if (st != stage) { searched = false; warned = false; stage = st; }
                epoch = StoryLight.Epoch;
                if (!searched && stage) Find();
            }

            float open = ExodusSea.Open;
            Apply(open);
            Hold(open);
            UpdateActors();
        }

        void OnDestroy()
        {
            if (hold) Destroy(hold.gameObject);
        }

        // ---------------- set nodes
        void Find()
        {
            searched = true;
            wallBack = wallFront = lane = null;
            lastScale = -1f; lastActive = -1; lastLane = -1;
            var all = stage.GetComponentsInChildren<Transform>(true);
            var byName = new Dictionary<string, Transform>();
            foreach (var t in all) if (!byName.ContainsKey(t.name)) byName[t.name] = t;
            if (!byName.ContainsKey("sea") && !byName.ContainsKey(WallBack)) return;   // not the Exodus set: nothing to do
            byName.TryGetValue(WallBack, out wallBack);
            byName.TryGetValue(WallFront, out wallFront);
            byName.TryGetValue(Lane, out lane);
            foreach (var w in new[] { wallBack, wallFront })
                if (w && !fullScale.ContainsKey(w))
                {   // modelled at full height and scaled to RestScale in y at rest (CONTRACT §6); accept an unscaled wall too
                    var s = w.localScale;
                    if (Mathf.Abs(s.y) < 0.2f) s.y /= ExodusSea.RestScale;
                    fullScale[w] = s;
                }
            ExodusFx.Boxes.Clear();
            foreach (var n in Measured)
                if (byName.TryGetValue(n, out var tr) && Measure(tr, Vector3.zero, out var bb)) ExodusFx.Boxes[n] = bb;
            Bounds bBack = default, bFront = default;
            bool hb = wallBack && Measure(wallBack, fullScale[wallBack], out bBack);
            bool hf = wallFront && Measure(wallFront, fullScale[wallFront], out bFront);
            if (hb) ExodusFx.Boxes[WallBack] = bBack;
            if (hf) ExodusFx.Boxes[WallFront] = bFront;
            if (hb && hf && Plausible(bBack) && Plausible(bFront) && bBack.max.z < bFront.min.z + 0.05f)
            {
                ExodusSea.X0 = Mathf.Min(bBack.min.x, bFront.min.x);
                ExodusSea.X1 = Mathf.Max(bBack.max.x, bFront.max.x);
                ExodusSea.ZBack = bBack.max.z;
                ExodusSea.ZFront = bFront.min.z;
                ExodusSea.BaseY = Mathf.Max(0f, Mathf.Min(bBack.min.y, bFront.min.y));
                ExodusSea.TopBackY = bBack.max.y;
                ExodusSea.TopFrontY = bFront.max.y;
            }
            string missing = (wallBack ? "" : " " + WallBack) + (wallFront ? "" : " " + WallFront) + (lane ? "" : " " + Lane);
            if (missing.Length > 0 && !warned)
            {
                warned = true;
                Debug.LogWarning($"[ExodusFx] set node(s){missing} not found under '{stage.name}'; the sea effects play without moving them.");
            }
            Apply(ExodusSea.Open, true);
        }

        static bool Plausible(Bounds b) =>
            b.size.x > 0.05f && b.size.x < 0.8f && b.size.y > 0.05f && b.size.y < 0.6f && Mathf.Abs(b.center.x) < 0.8f && Mathf.Abs(b.center.z) < 0.8f;

        /// <summary>Stage-local bounds of every mesh under 'root' (inactive included). scaleOverride != 0: measured with that
        /// localScale on root (the walls at full height), restored afterwards.</summary>
        bool Measure(Transform root, Vector3 scaleOverride, out Bounds bounds)
        {
            bounds = default;
            Vector3 keep = root.localScale;
            if (scaleOverride != Vector3.zero) root.localScale = scaleOverride;
            bool any = false;
            var mfs = root.GetComponentsInChildren<MeshFilter>(true);
            foreach (var mf in mfs)
            {
                var m = mf.sharedMesh; if (!m) continue;
                Encapsulate(ref bounds, ref any, m.bounds, mf.transform);
            }
            foreach (var sk in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                if (sk.sharedMesh) Encapsulate(ref bounds, ref any, sk.sharedMesh.bounds, sk.transform);
            if (scaleOverride != Vector3.zero) root.localScale = keep;
            return any;
        }

        void Encapsulate(ref Bounds bounds, ref bool any, Bounds local, Transform tr)
        {
            Vector3 mn = local.min, mx = local.max;
            for (int i = 0; i < 8; i++)
            {
                var c = new Vector3((i & 1) == 0 ? mn.x : mx.x, (i & 2) == 0 ? mn.y : mx.y, (i & 4) == 0 ? mn.z : mx.z);
                var p = stage.InverseTransformPoint(tr.TransformPoint(c));
                if (!any) { bounds = new Bounds(p, Vector3.zero); any = true; } else bounds.Encapsulate(p);
            }
        }

        void Apply(float open, bool force = false)
        {
            float sy = ExodusSea.ScaleY(open, ExodusSea.Clock);
            int active = open > 0.003f ? 1 : 0;
            if (force || active != lastActive || (active == 1 && Mathf.Abs(sy - lastScale) > 1e-5f))
            {
                foreach (var w in new[] { wallBack, wallFront })
                {
                    if (!w || !fullScale.TryGetValue(w, out var full)) continue;
                    w.localScale = new Vector3(full.x, full.y * sy, full.z);
                    if (w.gameObject.activeSelf != (active == 1)) w.gameObject.SetActive(active == 1);
                }
                lastScale = sy; lastActive = active;
            }
            int laneOn = ExodusSea.LaneHidden(open) ? 0 : 1;
            if (lane && (force || laneOn != lastLane))
            {
                if (lane.gameObject.activeSelf != (laneOn == 1)) lane.gameObject.SetActive(laneOn == 1);
                lastLane = laneOn;
            }
        }

        void Hold(float open)
        {
            if (open > 0.001f)
            {
                if (!hold && DGFx.Has("sea_hold"))
                {
                    Transform at = wallBack ? wallBack.parent : DGFx.Stage;
                    hold = DGFx.Spawn("sea_hold", at, 1e6f);
                }
            }
            else if (hold)
            {
                Destroy(hold.gameObject);
                hold = null;
            }
        }

        // ---------------- actors
        void UpdateActors()
        {
            if (!ExodusFx.ActorsWanted) { if (ExodusFx.Actors.Count > 0) ExodusFx.Actors.Clear(); return; }
            ExodusFx.ActorsWanted = false;   // effects set it again every frame they draw
            ExodusFx.Actors.Clear();
            if (!stage) return;
            actorScan -= Time.unscaledDeltaTime;
            if (actorScan <= 0f) { actorScan = 0.5f; actors = stage.GetComponentsInChildren<DGActor>(false); }
            foreach (var a in actors)
            {
                if (!a || !a.isActiveAndEnabled) continue;
                ExodusFx.Actors.Add(new ExodusActor { feet = stage.InverseTransformPoint(a.transform.position), height = a.height });
            }
        }
    }
}
