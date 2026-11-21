// Stand-ins for the Unity editor and desktop builds (Platform/Native.cs): no permission prompt, no vibration, sheets
// open in the computer's PDF viewer, launch arguments from the command line ("-demo esther").
using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace DoodLive.Platform
{
    public sealed class EditorPlatform : ICameraPermission, IHaptics, ISheetActions, IAudioSession, ILaunchArgs, IExternalActions, IStoragePaths
    {
        public bool Granted => true;
        public IEnumerator Request(Action<bool> done) { done?.Invoke(true); yield break; }

        public void Buzz(long ms) { }

        public string Run(string action, string streamingPath, string displayName, string title)
        {
            string path = Path.Combine(Application.streamingAssetsPath, streamingPath);
            if (!File.Exists(path)) return "error:missing " + streamingPath;
            Application.OpenURL(new Uri(path).AbsoluteUri);
            return "desktop";
        }

        public void ConfigureForStory() { }

        public string Get(string key)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-" + key) return a[i + 1];
            return null;
        }
        public bool GetBool(string key) { var v = Get(key); return v == "true" || v == "1"; }

        public void OpenUrl(string url) => Application.OpenURL(url);
        public void OpenAppSettings() { }

        public string PackCache => Path.Combine(Application.persistentDataPath, "packs");
        public bool StreamingFileMayExist(string path) => File.Exists(path);
    }
}
