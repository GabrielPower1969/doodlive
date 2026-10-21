// Port of animate() in web/angel.js. DoodLiveSetup samples it into the Enter / Idle / Blow AnimationClips;
// at runtime the Animator plays those clips (a Blender rig would ship its own clips instead).
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive
{
    public enum Phase { Enter, Idle, Blow }

    public static class AngelPose
    {
        public const float EnterLength = 1.4f, BlowLength = 3.3f;
        // Idle loops seamlessly over IdleLength: every idle frequency is rounded to a whole number of cycles.
        public const float IdleLength = 28f;

        public struct Pose
        {
            public float rootScale, rigY, rigSpin;            // rigSpin: three rig.rotation.y (radians)
            public Dictionary<string, Vector3> euler;          // three Euler XYZ (radians) per bone
        }

        static float Ease(float t) => t < 0 ? 0 : t > 1 ? 1 : t * t * (3 - 2 * t);
        static float EaseOutBack(float t) { const float c = 1.7f; t = Mathf.Clamp01(t); return 1 + (c + 1) * Mathf.Pow(t - 1, 3) + c * Mathf.Pow(t - 1, 2); }

        // Loop-safe angular frequency close to w (rad/s), for idle only.
        static float W(float w, Phase p) => p == Phase.Idle ? Mathf.Round(w * IdleLength / (2 * Mathf.PI)) * 2 * Mathf.PI / IdleLength : w;

        /// <summary>t = seconds in phase; time = global seconds (equal to t inside a clip).</summary>
        public static Pose Sample(Phase phase, float t, float time)
        {
            float S(float w, float x = 0) => Mathf.Sin(W(w, phase) * time + x);
            float flapAmp = 0.12f, flapSpeed = 1.6f, armR = 0, elbowR = 0, armL = 0, elbowL = 0, headX = 0, headZ = 0, lift = 0;
            var p = new Pose { rootScale = 1, rigSpin = 0, euler = new Dictionary<string, Vector3>() };

            if (phase == Phase.Enter)
            {
                p.rootScale = Mathf.Max(0.001f, EaseOutBack(t / 1.4f));
                p.rigSpin = (1 - Ease(t / 1.4f)) * Mathf.PI * 2;
                lift = (1 - Ease(t / 1.2f)) * -0.25f;
                flapAmp = 0.5f; flapSpeed = 6;
            }
            if (phase == Phase.Blow)
            {
                float up = Ease(t / 0.45f) * (1 - Ease((t - 2.6f) / 0.6f));
                armR = 1.05f * up; elbowR = -0.35f * up;
                armL = -0.75f * up + Mathf.Sin(t * 7) * 0.12f * up; elbowL = 0.4f * up;
                headX = -0.22f * up; headZ = 0.12f * up;
                flapAmp = 0.12f + 0.45f * up; flapSpeed = 1.6f + 6 * up;
                lift = 0.05f * up + 0.01f * Mathf.Sin(t * 20) * up;
            }

            p.rigY = lift + 0.018f * S(1.3f);
            p.euler["spine"] = new Vector3(0, 0, 0.02f * S(0.9f));
            p.euler["head"] = new Vector3(headX + 0.04f * S(0.7f), 0.08f * S(0.45f), headZ + 0.03f * S(0.8f));
            p.euler["shoulderR"] = new Vector3(0, 0, armR + 0.03f * S(1.1f));
            p.euler["elbowR"] = new Vector3(0, 0, elbowR);
            p.euler["shoulderL"] = new Vector3(0, 0, armL - 0.03f * S(1.1f, 1));
            p.euler["elbowL"] = new Vector3(0, 0, elbowL);

            // Flap phase is integrated (not speed * time) so speed changes inside Blow don't jump.
            float f = phase == Phase.Idle ? S(flapSpeed) : Mathf.Sin(FlapPhase(phase, t));
            const float back = 0.3f;
            p.euler["wingL"] = new Vector3(0, -back - flapAmp * f, 0.05f * f);
            p.euler["wingLmid"] = new Vector3(0, -0.08f - flapAmp * 0.6f * f, 0);
            p.euler["wingLtip"] = new Vector3(0, -0.05f - flapAmp * 0.4f * f, 0);
            p.euler["wingR"] = new Vector3(0, back + flapAmp * f, -0.05f * f);
            p.euler["wingRmid"] = new Vector3(0, 0.08f + flapAmp * 0.6f * f, 0);
            p.euler["wingRtip"] = new Vector3(0, 0.05f + flapAmp * 0.4f * f, 0);
            return p;
        }

        static float FlapPhase(Phase phase, float t)
        {
            if (phase == Phase.Enter) return 6 * t;
            // Blow: speed = 1.6 + 6 * up(t)
            float acc = 0, dt = 1 / 240f;
            for (float x = 0; x < t; x += dt)
            {
                float up = Ease(x / 0.45f) * (1 - Ease((x - 2.6f) / 0.6f));
                acc += (1.6f + 6 * up) * dt;
            }
            return acc;
        }

        /// <summary>three.js Euler XYZ (right-handed) to a Unity rotation of the z-mirrored model.</summary>
        public static Quaternion ToUnity(Vector3 e) =>
            Quaternion.AngleAxis(-e.x * Mathf.Rad2Deg, Vector3.right) *
            Quaternion.AngleAxis(-e.y * Mathf.Rad2Deg, Vector3.up) *
            Quaternion.AngleAxis(e.z * Mathf.Rad2Deg, Vector3.forward);
    }
}
