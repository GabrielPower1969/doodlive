// Story text in the extra languages (fr de ja es ar pt): titles, bookshelf blurbs, chapter titles and spoken lines.
// Chinese and English stay in the timelines and library.json as before; the other six come from
// Resources/i18n_stories.txt, written by tools/i18n/merge.py from assets/<story>/i18n.json (docs/I18N.md).
//
// The bookshelf and the subtitles keep their original look in Chinese and English: Chinese big, English small
// underneath (Pick(...).second). In the other languages there is one line, in that language; a missing translation
// falls back to English. Every getter returns logical order: call L10n.Show (one line) or ArabicText.Wrap (a
// paragraph) before drawing Arabic.
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive
{
    public static class StoryText
    {
        static Dictionary<string, string> table;

        static void Load()
        {
            table = new Dictionary<string, string>();
            var ta = Resources.Load<TextAsset>("i18n_stories");
            if (!ta) { Debug.LogWarning("DoodLive: Resources/i18n_stories.txt missing; stories show English in the extra languages"); return; }
            foreach (var row in ta.text.Split('\n'))
            {
                if (row.Length == 0 || row[0] == '#') continue;
                var c = row.Split('\t');
                if (c.Length < 3) continue;
                table[c[0] + "|" + c[1]] = c[2].TrimEnd('\r').Replace("\\n", "\n").Replace("\\\\", "\\");
            }
        }

        static string Get(string key, string lang)
        {
            if (table == null) Load();
            return table.TryGetValue(key + "|" + lang, out var s) ? s : null;
        }

        /// <summary>One string in the current language: zh / en from the caller's own fields, else the table, else English.</summary>
        public static string In(string key, string zh, string en, string lang = null)
        {
            lang = lang ?? L10n.Lang;
            if (lang == "zh") return zh;
            if (lang == "en") return en;
            return Get(key, lang) ?? en;
        }

        /// <summary>(main, second) for a two-line label. Chinese and English keep the original pair (Chinese, English);
        /// other languages show only their own text (second = null).</summary>
        public static (string main, string mainLang, string second) Pick(string key, string zh, string en)
        {
            var l = L10n.Lang;
            if (l == "zh" || l == "en") return (zh, "zh", en);
            return (Get(key, l) ?? en, Get(key, l) != null ? l : "en", null);
        }

        public static string Title(string story, string zh, string en) => In("t:" + story, zh, en);
        public static string Blurb(string story, string zh, string en) => In("b:" + story, zh, en);
        public static string Shot(string story, string shotId, string zh, string en) => In($"s:{story}:{shotId}", zh, en);
        public static string ShotAt(string story, int n, string zh, string en) => In($"si:{story}:{n}", zh, en);
        public static string Line(string story, string lineId, string zh, string en) => In($"l:{story}:{lineId}", zh, en);
    }
}
