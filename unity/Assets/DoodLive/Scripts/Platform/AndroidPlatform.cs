// Android answers for the platform layer (Platform/Native.cs). The JNI calls moved here unchanged from
// ARColoringController (2026-11-22): camera permission, Intent extras, vibrator, and the sheet actions in
// Plugins/Android/DoodLiveShare.java.
#if UNITY_ANDROID && !UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.Android;

namespace DoodLive.Platform
{
    public sealed class AndroidPlatform : ICameraPermission, IHaptics, ISheetActions, IAudioSession, ILaunchArgs, IExternalActions, IStoragePaths
    {
        static AndroidJavaObject Activity()
        {
            using var up = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
            return up.GetStatic<AndroidJavaObject>("currentActivity");
        }

        // ---- camera permission
        public bool Granted => Permission.HasUserAuthorizedPermission(Permission.Camera);
        public IEnumerator Request(Action<bool> done)
        {
            if (!Granted)
            {
                bool answered = false;
                var cb = new PermissionCallbacks();
                cb.PermissionGranted += _ => answered = true; cb.PermissionDenied += _ => answered = true; cb.PermissionDeniedAndDontAskAgain += _ => answered = true;
                Permission.RequestUserPermission(Permission.Camera, cb);
                while (!answered) yield return null;
            }
            done?.Invoke(Granted);
        }

        // ---- haptics
        public void Buzz(long ms)
        {
            try
            {
                using var act = Activity();
                using var vib = act.Call<AndroidJavaObject>("getSystemService", "vibrator");
                vib.Call("vibrate", ms);
            }
            catch { Handheld.Vibrate(); }   // also makes Unity add the VIBRATE permission
        }

        // ---- sheet actions: DoodLiveShare.run(activity, action, assetPath, displayName, title)
        public string Run(string action, string streamingPath, string displayName, string title)
        {
            try
            {
                using var act = Activity();
                using var share = new AndroidJavaClass("today.onemorething.doodlive.share.DoodLiveShare");
                return share.CallStatic<string>("run", act, action, streamingPath, displayName, title);
            }
            catch (Exception e) { return "error:" + e.Message; }
        }

        public void ConfigureForStory() { }   // Android plays media sound in silent mode already

        // ---- launch arguments: `adb shell am start ... --es demo esther --ez noimages true`
        string extraS(string key)
        {
            try { using var act = Activity(); using var intent = act.Call<AndroidJavaObject>("getIntent"); return intent.Call<string>("getStringExtra", key); }
            catch (Exception e) { Debug.LogWarning("DoodLive: intent read failed " + e.Message); return null; }
        }
        public string Get(string key) => extraS(key);
        public bool GetBool(string key)
        {
            try { using var act = Activity(); using var intent = act.Call<AndroidJavaObject>("getIntent"); return intent.Call<bool>("getBooleanExtra", key, false); }
            catch { return false; }
        }

        // ---- leaving the app (grown-ups area only)
        public void OpenUrl(string url) => Application.OpenURL(url);
        public void OpenAppSettings()
        {
            try
            {
                using var act = Activity();
                using var uriClass = new AndroidJavaClass("android.net.Uri");
                using var uri = uriClass.CallStatic<AndroidJavaObject>("fromParts", "package", Application.identifier, null);
                using var intent = new AndroidJavaObject("android.content.Intent", "android.settings.APPLICATION_DETAILS_SETTINGS", uri);
                act.Call("startActivity", intent);
            }
            catch (Exception e) { Debug.LogWarning("DoodLive: open settings failed " + e.Message); }
        }

        // ---- storage
        public string PackCache => Path.Combine(Application.persistentDataPath, "packs");
        public bool StreamingFileMayExist(string path) => true;   // inside the APK: cannot be checked with File.Exists
    }
}
#endif
