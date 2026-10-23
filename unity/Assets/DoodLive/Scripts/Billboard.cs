// Keeps the 3D title readable: turns about the world Y axis to face the camera and bobs gently.
using UnityEngine;

namespace DoodLive
{
    public class Billboard : MonoBehaviour
    {
        public float bobAmplitude = 0.02f, bobSpeed = 1.1f;
        public int frontSign = 1;   // +1: the text's readable side is local +Z, -1: local -Z (set by DoodLiveSetup)
        Vector3 start; Camera cam;

        void Start() { start = transform.localPosition; cam = Camera.main; }

        void LateUpdate()
        {
            if (!cam) cam = Camera.main;
            if (cam)
            {
                var to = cam.transform.position - transform.position; to.y = 0;
                if (to.sqrMagnitude > 1e-6f) transform.rotation = Quaternion.LookRotation(to.normalized * frontSign, Vector3.up);
            }
            transform.localPosition = start + Vector3.up * (Mathf.Sin(Time.time * bobSpeed) * bobAmplitude);
        }
    }
}
