// Arabic for IMGUI. Unity's IMGUI draws code points one by one, left to right, with no OpenType shaping, so Arabic
// would come out as separate, unjoined letters in the wrong order. This class does the two missing steps:
//   1. shaping: each letter becomes its isolated / final / initial / medial presentation form (Unicode Arabic
//      Presentation Forms-B, U+FE70-U+FEFF, which Noto Sans Arabic maps), lam + alef become one ligature;
//   2. visual order: the line is reversed for right-to-left, while runs of Latin letters and digits keep their own
//      left-to-right order, and brackets are mirrored.
// Wrap() breaks a paragraph into lines first (measured with the style), because IMGUI's own word wrap would put the
// end of the sentence on the first line once the text is reversed. Pure C#, no external library.
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace DoodLive
{
    public static class ArabicText
    {
        // letter -> isolated, final, initial, medial (0 = the letter does not join forward: no initial / medial form)
        static readonly Dictionary<char, char[]> Forms = new Dictionary<char, char[]>
        {
            { 'ء', new[] { 'ﺀ', 'ﺀ', '\0', '\0' } },             // hamza: never joins
            { 'آ', new[] { 'ﺁ', 'ﺂ', '\0', '\0' } },
            { 'أ', new[] { 'ﺃ', 'ﺄ', '\0', '\0' } },
            { 'ؤ', new[] { 'ﺅ', 'ﺆ', '\0', '\0' } },
            { 'إ', new[] { 'ﺇ', 'ﺈ', '\0', '\0' } },
            { 'ئ', new[] { 'ﺉ', 'ﺊ', 'ﺋ', 'ﺌ' } },
            { 'ا', new[] { 'ﺍ', 'ﺎ', '\0', '\0' } },
            { 'ب', new[] { 'ﺏ', 'ﺐ', 'ﺑ', 'ﺒ' } },
            { 'ة', new[] { 'ﺓ', 'ﺔ', '\0', '\0' } },
            { 'ت', new[] { 'ﺕ', 'ﺖ', 'ﺗ', 'ﺘ' } },
            { 'ث', new[] { 'ﺙ', 'ﺚ', 'ﺛ', 'ﺜ' } },
            { 'ج', new[] { 'ﺝ', 'ﺞ', 'ﺟ', 'ﺠ' } },
            { 'ح', new[] { 'ﺡ', 'ﺢ', 'ﺣ', 'ﺤ' } },
            { 'خ', new[] { 'ﺥ', 'ﺦ', 'ﺧ', 'ﺨ' } },
            { 'د', new[] { 'ﺩ', 'ﺪ', '\0', '\0' } },
            { 'ذ', new[] { 'ﺫ', 'ﺬ', '\0', '\0' } },
            { 'ر', new[] { 'ﺭ', 'ﺮ', '\0', '\0' } },
            { 'ز', new[] { 'ﺯ', 'ﺰ', '\0', '\0' } },
            { 'س', new[] { 'ﺱ', 'ﺲ', 'ﺳ', 'ﺴ' } },
            { 'ش', new[] { 'ﺵ', 'ﺶ', 'ﺷ', 'ﺸ' } },
            { 'ص', new[] { 'ﺹ', 'ﺺ', 'ﺻ', 'ﺼ' } },
            { 'ض', new[] { 'ﺽ', 'ﺾ', 'ﺿ', 'ﻀ' } },
            { 'ط', new[] { 'ﻁ', 'ﻂ', 'ﻃ', 'ﻄ' } },
            { 'ظ', new[] { 'ﻅ', 'ﻆ', 'ﻇ', 'ﻈ' } },
            { 'ع', new[] { 'ﻉ', 'ﻊ', 'ﻋ', 'ﻌ' } },
            { 'غ', new[] { 'ﻍ', 'ﻎ', 'ﻏ', 'ﻐ' } },
            { 'ـ', new[] { 'ـ', 'ـ', 'ـ', 'ـ' } },     // tatweel
            { 'ف', new[] { 'ﻑ', 'ﻒ', 'ﻓ', 'ﻔ' } },
            { 'ق', new[] { 'ﻕ', 'ﻖ', 'ﻗ', 'ﻘ' } },
            { 'ك', new[] { 'ﻙ', 'ﻚ', 'ﻛ', 'ﻜ' } },
            { 'ل', new[] { 'ﻝ', 'ﻞ', 'ﻟ', 'ﻠ' } },
            { 'م', new[] { 'ﻡ', 'ﻢ', 'ﻣ', 'ﻤ' } },
            { 'ن', new[] { 'ﻥ', 'ﻦ', 'ﻧ', 'ﻨ' } },
            { 'ه', new[] { 'ﻩ', 'ﻪ', 'ﻫ', 'ﻬ' } },
            { 'و', new[] { 'ﻭ', 'ﻮ', '\0', '\0' } },
            { 'ى', new[] { 'ﻯ', 'ﻰ', '\0', '\0' } },
            { 'ي', new[] { 'ﻱ', 'ﻲ', 'ﻳ', 'ﻴ' } },
        };
        // lam + this alef -> ligature (isolated, final)
        static readonly Dictionary<char, char[]> LamAlef = new Dictionary<char, char[]>
        {
            { 'آ', new[] { 'ﻵ', 'ﻶ' } },
            { 'أ', new[] { 'ﻷ', 'ﻸ' } },
            { 'إ', new[] { 'ﻹ', 'ﻺ' } },
            { 'ا', new[] { 'ﻻ', 'ﻼ' } },
        };

        static bool Mark(char c) => (c >= 'ً' && c <= 'ٟ') || c == 'ٰ';     // harakat: see through
        static bool Joins(char c) => Forms.ContainsKey(c) && c != 'ء';
        static bool JoinsForward(char c) => Forms.TryGetValue(c, out var f) && f[2] != '\0';
        public static bool IsArabic(char c) => (c >= '؀' && c <= 'ۿ') || (c >= 'ﭐ' && c <= '﷿') || (c >= 'ﹰ' && c <= '﻿');
        public static bool HasArabic(string s) { if (s == null) return false; foreach (var c in s) if (IsArabic(c)) return true; return false; }

        /// <summary>Logical Arabic -> presentation forms, still in logical order.</summary>
        public static string Shape(string s)
        {
            var sb = new StringBuilder(s.Length);
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (!Forms.TryGetValue(c, out var f)) { sb.Append(c); continue; }
                int p = i - 1; while (p >= 0 && Mark(s[p])) p--;
                int n = i + 1; while (n < s.Length && Mark(s[n])) n++;
                bool fromPrev = p >= 0 && JoinsForward(s[p]) && Joins(c);
                if (c == 'ل' && n < s.Length && LamAlef.TryGetValue(s[n], out var la))
                {
                    sb.Append(fromPrev ? la[1] : la[0]);
                    for (int k = i + 1; k < n; k++) sb.Append(s[k]);   // marks between lam and alef
                    i = n; continue;
                }
                bool toNext = n < s.Length && JoinsForward(c) && Joins(s[n]);
                sb.Append(fromPrev && toNext ? f[3] : fromPrev ? f[1] : toNext ? f[2] : f[0]);
            }
            return sb.ToString();
        }

        static bool StrongLtr(char c) => (c < 0x0590 && char.IsLetterOrDigit(c)) || (c >= '0' && c <= '9');
        static char Mirror(char c) => c == '(' ? ')' : c == ')' ? '(' : c == '[' ? ']' : c == ']' ? '[' : c == '«' ? '»' : c == '»' ? '«' : c == '<' ? '>' : c == '>' ? '<' : c;

        /// <summary>One line, logical order -> shaped and in visual (left-to-right drawing) order.</summary>
        public static string Visual(string s)
        {
            if (string.IsNullOrEmpty(s) || !HasArabic(s)) return s;
            if (s.IndexOf('\n') >= 0)
            {
                var parts = s.Split('\n');
                for (int k = 0; k < parts.Length; k++) parts[k] = Visual(parts[k]);
                return string.Join("\n", parts);
            }
            string shaped = Shape(s);
            // runs: a left-to-right run is strong Latin letters / digits plus what sits between two of them (spaces,
            // dots, colons inside "1:2" or "A4"); everything else reads right to left
            var runs = new List<(bool ltr, string text)>();
            int i = 0;
            while (i < shaped.Length)
            {
                if (StrongLtr(shaped[i]))
                {
                    int j = i + 1, lastStrong = i;
                    while (j < shaped.Length && !IsArabic(shaped[j]))
                    {
                        if (StrongLtr(shaped[j])) lastStrong = j;
                        j++;
                    }
                    runs.Add((true, shaped.Substring(i, lastStrong - i + 1))); i = lastStrong + 1;
                }
                else
                {
                    int j = i + 1;
                    while (j < shaped.Length && !StrongLtr(shaped[j])) j++;
                    runs.Add((false, shaped.Substring(i, j - i))); i = j;
                }
            }
            var sb = new StringBuilder(shaped.Length);
            for (int r = runs.Count - 1; r >= 0; r--)
            {
                if (runs[r].ltr) { sb.Append(runs[r].text); continue; }
                var t = runs[r].text;
                for (int k = t.Length - 1; k >= 0; k--)
                {
                    char c = t[k];
                    if (Mark(c)) continue;                     // harakat cannot be placed without shaping: drop them
                    sb.Append(Mirror(c));
                }
            }
            return sb.ToString();
        }

        /// <summary>Break a logical-order paragraph into lines no wider than `width` in `style`, then make each line
        /// visual. The result has explicit line breaks, so the label must not wrap again (it never needs to).</summary>
        public static string Wrap(string s, GUIStyle style, float width)
        {
            if (string.IsNullOrEmpty(s) || !HasArabic(s)) return s;
            var lines = new List<string>();
            foreach (var para in s.Split('\n'))
            {
                var words = para.Split(' ');
                string cur = "";
                foreach (var w in words)
                {
                    string next = cur.Length == 0 ? w : cur + " " + w;
                    if (cur.Length > 0 && style.CalcSize(new GUIContent(Visual(next))).x > width) { lines.Add(cur); cur = w; }
                    else cur = next;
                }
                lines.Add(cur);
            }
            for (int k = 0; k < lines.Count; k++) lines[k] = Visual(lines[k]);
            return string.Join("\n", lines);
        }
    }
}
