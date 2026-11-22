// The platform layer (docs/PLATFORM-ARCHITECTURE.md §1.3): the only place that knows which system the app runs on.
// The rest of the app asks for a thing ("buzz", "ask for the camera", "print this sheet") through these small
// interfaces and never names Android or iOS. Each system answers with its own class:
//   AndroidPlatform.cs   JNI calls + Plugins/Android/DoodLiveShare.java
//   IosPlatform.cs       Plugins/iOS/DoodLivePlatform.mm (haptics, share / print, audio session)
//   EditorPlatform.cs    the Unity editor and desktop builds: safe stand-ins
// Rule (checked by scripts/build-apk.sh): `UNITY_ANDROID`, `UNITY_IOS`, `AndroidJava*`, `UnityEngine.Android` and
// `DllImport("__Internal")` appear only in this folder and in Editor/ build scripts.
using System;
using System.Collections;

namespace DoodLive.Platform
{
    /// <summary>Camera permission. Request() yields until the person answers; done(true) = granted.</summary>
    public interface ICameraPermission { IEnumerator Request(Action<bool> done); bool Granted { get; } }

    /// <summary>A short vibration (button tap, the stage landing on the table).</summary>
    public interface IHaptics { void Buzz(long ms); }

    /// <summary>Save / share / print a sheet PDF from StreamingAssets with the system's own screens.
    /// Returns "saved:&lt;where&gt;", "shared", "printing", "desktop" (opened in a viewer) or "error:&lt;why&gt;".</summary>
    public interface ISheetActions { string Run(string action, string streamingPath, string displayName, string title); }

    /// <summary>How the app's sound mixes with the system (iOS: play the story even with the silent switch on).</summary>
    public interface IAudioSession { void ConfigureForStory(); }

    /// <summary>Launch arguments for QA and demo recordings (Android: Intent extras; iOS: process arguments "-key value").</summary>
    public interface ILaunchArgs { string Get(string key); bool GetBool(string key); }

    /// <summary>Things that leave the app. Only call them from behind the grown-ups gate (store rules for kids apps).</summary>
    public interface IExternalActions { void OpenUrl(string url); void OpenAppSettings(); }

    /// <summary>Where files live. StreamingFileExists is false-negative-free: on Android the file sits inside the APK
    /// and cannot be checked, so it says true and the caller finds out when it loads.</summary>
    public interface IStoragePaths { string PackCache { get; } bool StreamingFileMayExist(string path); }

    public static class Native
    {
        static readonly object impl =
#if UNITY_EDITOR
            new EditorPlatform();
#elif UNITY_ANDROID
            new AndroidPlatform();
#elif UNITY_IOS
            new IosPlatform();
#else
            new EditorPlatform();
#endif
        public static ICameraPermission Camera => (ICameraPermission)impl;
        public static IHaptics Haptics => (IHaptics)impl;
        public static ISheetActions Sheets => (ISheetActions)impl;
        public static IAudioSession Audio => (IAudioSession)impl;
        public static ILaunchArgs Args => (ILaunchArgs)impl;
        public static IExternalActions External => (IExternalActions)impl;
        public static IStoragePaths Storage => (IStoragePaths)impl;
        public static string Name => impl.GetType().Name;
    }
}
