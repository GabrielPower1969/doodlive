// Runtime side of the prodigal son effects (docs/prodigal/FX.md "Wiring for Integration").
// A hidden singleton (auto-created, runs before every DGFxInstance) that finds the set's lamp empties (`lampsFlame*`,
// CONTRACT §6) under DGFx.Stage and writes their stage-local positions into ProdigalFx.Lamps every frame, so one
// lamps_flames call lights every lamp and lantern. It rescans when the stage changes, when DGFx.StopAll has run
// (StoryLight.Epoch: a new story / replay / seek), and, while lamps_flames is playing and none were found, once a second.
// No set, no lamps: the list stays empty and lamps_flames falls back to its anchor / the CONTRACT points (never throws).
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    [DefaultExecutionOrder(-20)]   // before DGFxInstance (0): the effect reads this frame's lamp positions
    public sealed class ProdigalStage : MonoBehaviour
    {
        static ProdigalStage inst;
        Transform stage;
        int epoch = int.MinValue;
        float retry;
        bool logged;
        readonly List<Transform> lamps = new List<Transform>(8);

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        public static void Ensure()
        {
            if (inst) return;
            var go = new GameObject("ProdigalStage") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            inst = go.AddComponent<ProdigalStage>();
        }

        void LateUpdate()
        {
            var st = DGFx.Stage;
            bool wanted = ProdigalFx.LampsWanted;
            ProdigalFx.LampsWanted = false;   // lamps_flames sets it again every frame it draws
            if (st != stage || epoch != StoryLight.Epoch)
            {
                if (st != stage) logged = false;
                stage = st; epoch = StoryLight.Epoch;
                Scan();
            }
            else if (wanted && lamps.Count == 0)
            {
                retry -= Time.unscaledDeltaTime;
                if (retry <= 0f) { retry = 1f; Scan(); }
            }

            var list = ProdigalFx.Lamps;
            list.Clear();
            if (!stage) return;
            for (int i = lamps.Count - 1; i >= 0; i--) if (!lamps[i]) lamps.RemoveAt(i);   // set destroyed / swapped
            foreach (var l in lamps) list.Add(stage.InverseTransformPoint(l.position));
            if (wanted && lamps.Count == 0 && !logged)
            {
                logged = true;
                Debug.LogWarning($"[ProdigalFx] no '{ProdigalFx.LampPrefix}*' empties under '{stage.name}'; lamps_flames lights its anchor / the CONTRACT points.");
            }
        }

        void Scan()
        {
            lamps.Clear();
            if (!stage) return;
            foreach (var t in stage.GetComponentsInChildren<Transform>(true))
                if (IsLamp(t) && !HasLampChild(t)) lamps.Add(t);   // empties only; a group node of lamp empties is skipped
        }

        static bool IsLamp(Transform t) =>
            t.name.StartsWith(ProdigalFx.LampPrefix, System.StringComparison.Ordinal) && !t.GetComponent<MeshFilter>();

        static bool HasLampChild(Transform t)
        {
            for (int i = 0; i < t.childCount; i++) if (IsLamp(t.GetChild(i))) return true;
            return false;
        }

        void OnDestroy() => ProdigalFx.Lamps.Clear();
    }
}
