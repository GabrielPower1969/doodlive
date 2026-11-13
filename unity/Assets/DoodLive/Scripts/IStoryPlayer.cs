// What the app (ARColoringController + its UI) needs from a story on the page, whichever engine plays it:
// DavidGoliath.DGDirector (story pack #1, its own director) or Story.StoryDirector (every later pack).
// docs/STORY-ARCHITECTURE.md; the UI draws subtitles, shot titles, the pause card and the replay chip from these.
using DoodLive.DavidGoliath;
using UnityEngine;

namespace DoodLive
{
    public interface IStoryPlayer
    {
        string StoryId { get; }
        bool Running { get; }
        bool Finished { get; }
        bool Paused { get; set; }
        bool Hold { get; set; }
        DGLine Line { get; }
        float LineAge { get; }
        DGShot Shot { get; }
        float ShotAge { get; }
        DGTimeline Timeline { get; }
        float MusicGain { get; set; }
        Camera Cinematic { get; set; }
        GameObject gameObject { get; }
        Transform transform { get; }
        void Begin();
        void Replay();
        void Stop();
        void TogglePause();
        void ShowDemoPage(bool on);
    }
}
