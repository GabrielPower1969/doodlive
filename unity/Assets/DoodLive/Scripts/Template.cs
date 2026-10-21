// Sheet geometry, read from template.json (copied from web/assets by DoodLiveSetup; never hand-edited).
using System;
using System.Globalization;
using UnityEngine;

namespace DoodLive
{
    [Serializable]
    public class Template
    {
        public Vector2 page;          // sheet size in template px (1240 x 1754)
        public Rect art;              // line-art rectangle in template px (x, y from the top-left)
        public Vector2[] markers;     // 4 marker centres, TL TR BR BL
        public Vector2 artPixels;     // source line-art size (1128 x 1384): model aspect

        public float ArtAspect => artPixels.y / artPixels.x;

        public static Template Load()
        {
            var json = Resources.Load<TextAsset>("template");
            if (json == null) throw new Exception("Resources/template.json missing: run DoodLive > Setup Project");
            return Parse(json.text);
        }

        public static Template Parse(string s)
        {
            var t = new Template();
            var p = Numbers(s, "page");
            var a = Numbers(s, "art");
            var m = Numbers(s, "markers");
            var ap = Numbers(s, "artPixels");
            t.page = new Vector2(p[0], p[1]);
            t.art = new Rect(a[0], a[1], a[2], a[3]);
            t.markers = new Vector2[4];
            for (int i = 0; i < 4; i++) t.markers[i] = new Vector2(m[i * 2], m[i * 2 + 1]);
            t.artPixels = new Vector2(ap[0], ap[1]);
            return t;
        }

        // All numbers of the (possibly nested) array that follows "key": in a flat JSON object.
        static float[] Numbers(string s, string key)
        {
            int k = s.IndexOf("\"" + key + "\"", StringComparison.Ordinal);
            if (k < 0) throw new Exception("template.json: no " + key);
            int i = s.IndexOf('[', k), depth = 0, start = -1;
            var list = new System.Collections.Generic.List<float>();
            for (; i < s.Length; i++)
            {
                char c = s[i];
                bool num = char.IsDigit(c) || c == '-' || c == '.' || c == 'e' || c == 'E' || c == '+';
                if (num) { if (start < 0) start = i; continue; }
                if (start >= 0) { list.Add(float.Parse(s.Substring(start, i - start), CultureInfo.InvariantCulture)); start = -1; }
                if (c == '[') depth++;
                else if (c == ']' && --depth == 0) break;
            }
            return list.ToArray();
        }
    }
}
