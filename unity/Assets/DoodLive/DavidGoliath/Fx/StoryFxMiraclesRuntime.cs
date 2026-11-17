// Runtime side of calm_wave (docs/miracles/FX.md). A hidden singleton drains MiraclesFx.EndRequests once per frame and
// destroys the running effect instances with those ids (storm_rain, tension_dim). The stage tint and dim they posted
// (StoryTint / StoryLight) are not renewed any more and expire by themselves. Same pattern as StoryFxStage (Esther).
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    public sealed class StoryFxMiraclesRuntime : MonoBehaviour
    {
        static StoryFxMiraclesRuntime inst;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        public static void Ensure()
        {
            if (inst) return;
            var go = new GameObject("StoryFxMiraclesRuntime") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            inst = go.AddComponent<StoryFxMiraclesRuntime>();
        }

        // After every effect's LateUpdate has run is not guaranteed, so a request posted this frame may be handled next frame.
        void LateUpdate()
        {
            var req = MiraclesFx.EndRequests;
            if (req.Count == 0) return;
            foreach (var i in DGFxInstance.Live.ToArray())
                if (i && req.Contains(i.Id)) Destroy(i.gameObject);
            req.Clear();
        }
    }
}
