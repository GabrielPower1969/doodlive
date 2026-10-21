// Continuous halo / cloud motion that the looping clips don't carry (angel.js: halo z 0.6 rad/s, cloud y 0.1 rad/s + bob).
using UnityEngine;

namespace DoodLive
{
    public class Spin : MonoBehaviour
    {
        public Vector3 axis = Vector3.forward;
        public float radiansPerSecond = 0.6f;
        public float bobAmplitude, bobSpeed = 0.8f;
        Vector3 start;

        void Awake() => start = transform.localPosition;

        void Update()
        {
            transform.Rotate(axis, -radiansPerSecond * Mathf.Rad2Deg * Time.deltaTime, Space.Self); // mirrored handedness
            if (bobAmplitude != 0) transform.localPosition = start + Vector3.up * (-bobAmplitude * Mathf.Sin(Time.time * bobSpeed));
        }
    }
}
