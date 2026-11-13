// One sheet the app has found, from either detection path:
//   - ARCore image tracking (ARTrackedImage): coloured pages and sheets on a screen, where ARCore has features to use;
//   - the 4 printed corner markers (SheetFinder + Vision/MarkerDetector): any sheet, blank or coloured (LESSONS L49).
// Pose convention = ARTrackedImage: local x = page right, local z = page top, local y = out of the page, origin = page
// centre; size = page width x height in metres.
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;

namespace DoodLive
{
    public sealed class SheetTarget
    {
        public readonly ARTrackedImage Image;     // set for the image-tracking path
        readonly Transform pose;                   // marker path: the finder's anchored pose object
        public string Name;                        // reference name ("david-goliath-A4", "fiery-p1", ...)
        public Vector2 MarkerSize;                 // marker path: page size in metres
        public Vector2[] ScreenMarkers;            // marker path: last marker centres TL TR BR BL, screen px (y up)
        public float LastSeen;                     // marker path: Time.time of the last detection

        public SheetTarget(ARTrackedImage image) { Image = image; Name = image.referenceImage.name; }
        public SheetTarget(Transform pose, string name) { this.pose = pose; Name = name; }

        public Transform transform => Image ? Image.transform : pose;
        public Vector2 size => Image ? Image.size : MarkerSize;
        public bool IsAlive => Image ? Image : pose;

        /// <summary>Seen now: image tracking state, or a marker detection within the last second.</summary>
        public bool Tracking => Image ? Image.trackingState == TrackingState.Tracking : pose && Time.time - LastSeen < 1.0f;
    }
}
