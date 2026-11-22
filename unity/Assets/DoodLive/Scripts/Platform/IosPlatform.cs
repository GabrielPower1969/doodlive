// iOS / iPadOS answers for the platform layer (Platform/Native.cs). Native side: Plugins/iOS/DoodLivePlatform.mm.
// Not yet run on a device (2026-11-22): written with the design review; first device test is phase 2 of
// docs/PLATFORM-ARCHITECTURE.md.
#if UNITY_IOS && !UNITY_EDITOR
using System;
using System.Collections;
using System.IO;
using System.Runtime.InteropServices;
using UnityEngine;

namespace DoodLive.Platform
{
    public sealed class IosPlatform : ICameraPermission, IHaptics, ISheetActions, IAudioSession, ILaunchArgs, IExternalActions, IStoragePaths
    {
        [DllImport("__Internal")] static extern void DLHaptic(int strength);                 // 0 light, 1 medium
        [DllImport("__Internal")] static extern void DLShareFile(string path, string title);  // share sheet ("Save to Files" is in it)
        [DllImport("__Internal")] static extern void DLPrintFile(string path, string title);  // AirPrint, A4 preselected
        [DllImport("__Internal")] static extern void DLAudioPlayback();                       // AVAudioSessionCategoryPlayback
        [DllImport("__Internal")] static extern void DLOpenSettings();

        public bool Granted => Application.HasUserAuthorization(UserAuthorization.WebCam);
        public IEnumerator Request(Action<bool> done)
        {
            if (!Granted) yield return Application.RequestUserAuthorization(UserAuthorization.WebCam);
            done?.Invoke(Granted);
        }

        public void Buzz(long ms) => DLHaptic(ms >= 40 ? 1 : 0);

        public string Run(string action, string streamingPath, string displayName, string title)
        {
            string path = Path.Combine(Application.streamingAssetsPath, streamingPath);
            if (!File.Exists(path)) return "error:missing " + streamingPath;
            // the share sheet needs the file under its display name: copy it to the temporary folder first
            string tmp = Path.Combine(Application.temporaryCachePath, displayName);
            try { File.Copy(path, tmp, true); } catch (Exception e) { return "error:" + e.Message; }
            if (action == "print") { DLPrintFile(tmp, title); return "printing"; }
            DLShareFile(tmp, title);   // "save" and "share" both open the share sheet; it has "Save to Files"
            return "shared";
        }

        public void ConfigureForStory() => DLAudioPlayback();

        public string Get(string key)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-" + key) return a[i + 1];
            return null;
        }
        public bool GetBool(string key) { var v = Get(key); return v == "true" || v == "1"; }

        public void OpenUrl(string url) => Application.OpenURL(url);
        public void OpenAppSettings() => DLOpenSettings();

        public string PackCache => Path.Combine(Application.persistentDataPath, "packs");
        public bool StreamingFileMayExist(string path) => File.Exists(path);
    }
}
#endif
