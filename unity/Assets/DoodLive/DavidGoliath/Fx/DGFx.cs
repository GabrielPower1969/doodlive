// Public entry point for the David & Goliath effects (CONTRACT §8, docs/david-goliath/FX.md).
//   DGFx.Stage = <transform whose local unit is one art width, page at local y = 0>;   // set once by DGDirector
//   DGFx.Play("dust_puff", goliathFootL, 0.6f);                                         // per timeline fx entry
// Everything is built in code: one shared procedural atlas, two unlit materials, one dynamic mesh per effect.
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    public static class DGFx
    {
        /// <summary>Space the effects live in: local unit = 1 art width, local y = 0 is the page (the character holder).
        /// When null, effects fall back to the root of the 'at' transform (logged once).</summary>
        public static Transform Stage;

        /// <summary>Optional child of Stage (identity rest pose, between Stage and the characters) that ground_shake moves.
        /// Never point it at a transform another script also positions (e.g. the AR holder itself).</summary>
        public static Transform ShakeTarget
        {
            get => shakeTarget;
            set
            {
                if (shakeTarget) shakeTarget.localPosition = shakeRest;
                shakeTarget = value;
                if (value) shakeRest = value.localPosition;
            }
        }

        /// <summary>Freeze every running effect (and the shake) without destroying it, e.g. while the play is paused.</summary>
        public static bool Paused;

        /// <summary>Multiplies effect time (1 = real time).</summary>
        public static float TimeScale = 1f;

        /// <summary>When true, a soft white full-screen flash is drawn with IMGUI for hit_flash. Set false to draw your own
        /// using <see cref="FlashAlpha"/>.</summary>
        public static bool DrawFlashOverlay = true;

        /// <summary>Current stage-local shake offset (art units). Applied to ShakeTarget when it is set.</summary>
        public static Vector3 ShakeOffset { get; internal set; }

        /// <summary>Current screen flash opacity 0..1.</summary>
        public static float FlashAlpha { get; internal set; }

        /// <summary>Every id this build can play (the timeline's fx ids).</summary>
        public static IEnumerable<string> Ids => FxLibrary.All.Keys;

        public static bool Has(string id) => FxLibrary.Get(id) != null;

        /// <summary>CONTRACT §8 entry point. Unknown ids log a warning and do nothing (never throw mid-performance).
        /// dur &lt;= 0 uses the effect's designed duration.</summary>
        public static void Play(string id, Transform at, float dur) => Spawn(id, at, dur);

        /// <summary>Same as Play, but returns the running instance (null for an unknown id).</summary>
        public static DGFxInstance Spawn(string id, Transform at, float dur, int seed = 0)
        {
            var def = FxLibrary.Get(id);
            if (def == null)
            {
                Debug.LogWarning($"[DGFx] unknown fx id '{id}' (known: {string.Join(", ", Ids)})");
                return null;
            }
            var stage = Stage;
            if (!stage)
            {
                stage = at ? at.root : null;
                if (!warnedStage) { warnedStage = true; Debug.LogWarning("[DGFx] DGFx.Stage not set; using the anchor's root as the stage."); }
            }
            DGFxRunner.Ensure();
            var go = new GameObject("DGFx_" + id);
            go.layer = stage ? stage.gameObject.layer : 0;
            var tr = go.transform;
            tr.SetParent(stage, false);
            tr.localPosition = Vector3.zero; tr.localRotation = Quaternion.identity; tr.localScale = Vector3.one;
            var inst = go.AddComponent<DGFxInstance>();
            inst.Init(def, at, dur > 0 ? dur : def.DefaultDur, seed != 0 ? seed : NextSeed());
            if (def.ShakeAmp > 0) Shake(def.ShakeAmp, def.ShakeDur);
            if (def.Flash > 0) Flash(def.Flash);
            return inst;
        }

        /// <summary>Shake the stage: amplitude in art units, decays to zero over dur seconds. Overlapping shakes add.</summary>
        public static void Shake(float amplitude, float dur)
        {
            if (amplitude <= 0 || dur <= 0) return;
            DGFxRunner.Ensure();
            DGFxRunner.AddShake(amplitude, dur);
        }

        /// <summary>Soft full-screen flash (0..1), fades in ~0.3 s.</summary>
        public static void Flash(float strength)
        {
            DGFxRunner.Ensure();
            FlashAlpha = Mathf.Max(FlashAlpha, Mathf.Clamp01(strength));
        }

        /// <summary>Destroy every running effect and reset shake / flash (on replay, seek, or leaving the sheet).</summary>
        public static void StopAll()
        {
            foreach (var i in DGFxInstance.Live.ToArray()) if (i) Object.Destroy(i.gameObject);
            DGFxInstance.Live.Clear();
            DGFxRunner.ClearShake();
            FlashAlpha = 0;
        }

        /// <summary>Build the atlas and materials now (about 1M pixel evaluations) instead of on the first Play.</summary>
        public static void Prewarm() => DGFxAssets.Ensure();

        static bool warnedStage;
        static int seedCounter = 1;
        static int NextSeed() => unchecked(seedCounter++ * 7919 + 17);

        static Transform shakeTarget;
        internal static Vector3 shakeRest;
    }
}
