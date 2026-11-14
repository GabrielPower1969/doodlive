// Bundles each book's colouring-sheet PDFs for the book-page actions (save / share / print; docs/LIBRARY.md
// "Sheet actions"): the blank sheet and the coloured sample. Called from DoodLiveSetup.Setup. Generated, never hand-edit:
//   print/<sheet>.pdf         -> Assets/StreamingAssets/sheets/<sheet>.pdf           (sheet = assets/stories.json
//   print/<sheet>-colored.pdf -> Assets/StreamingAssets/sheets/<sheet>-colored.pdf    sheets[0]; the angel book uses
//                                (tools/story/make_colored_pdf.py)                    doodlive-angel-A4)
//   Assets/DoodLive/Resources/sheet_pdfs.json =
//     {"sheets":[{"book":"<library id>","file":"<sheet>.pdf","colored":"<sheet>-colored.pdf"}, ...]}
// A story whose blank PDF is missing is left out of the index, and its book page hides the row. A story with no
// coloured PDF has "colored": "" and its book page offers the blank sheet only.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace DoodLive.EditorTools
{
    public static class SheetPdfSetup
    {
        [Serializable] class Reg { public Entry[] stories; }
        [Serializable] class Entry { public string id; public string[] sheets; }
        [Serializable] public class Item { public string book, file, colored = ""; }
        [Serializable] public class Index { public Item[] sheets; }

        public const string OutDir = "Assets/StreamingAssets/sheets";
        public const string IndexPath = "Assets/DoodLive/Resources/sheet_pdfs.json";
        public const string ColoredSuffix = "-colored";   // print/<sheet>-colored.pdf = the coloured sample
        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));

        public static void Copy()
        {
            var want = new List<(string book, string sheet)> { ("angel", "doodlive-angel-A4") };
            var reg = JsonUtility.FromJson<Reg>(File.ReadAllText(Path.Combine(RepoRoot, "assets/stories.json")));
            foreach (var s in reg.stories)
                if (s.sheets != null && s.sheets.Length > 0 && !string.IsNullOrEmpty(s.sheets[0])) want.Add((s.id, s.sheets[0]));

            Directory.CreateDirectory(OutDir);
            var items = new List<Item>();
            foreach (var (book, sheet) in want)
            {
                string src = Path.Combine(RepoRoot, "print", sheet + ".pdf"), dst = $"{OutDir}/{sheet}.pdf";
                if (!File.Exists(src)) { Debug.LogWarning($"Sheet PDF missing for {book}: {src} (its book page hides save / share / print)"); continue; }
                if (!File.Exists(dst) || !File.ReadAllBytes(dst).SequenceEqual(File.ReadAllBytes(src))) File.Copy(src, dst, true);
                var item = new Item { book = book, file = sheet + ".pdf" };
                string csrc = Path.Combine(RepoRoot, "print", sheet + ColoredSuffix + ".pdf"), cdst = $"{OutDir}/{sheet}{ColoredSuffix}.pdf";
                if (!File.Exists(csrc)) Debug.LogWarning($"Coloured sample PDF missing for {book}: {csrc} (its book page offers the blank sheet only; python3 tools/story/make_colored_pdf.py {book})");
                else
                {
                    if (!File.Exists(cdst) || !File.ReadAllBytes(cdst).SequenceEqual(File.ReadAllBytes(csrc))) File.Copy(csrc, cdst, true);
                    item.colored = sheet + ColoredSuffix + ".pdf";
                }
                items.Add(item);
            }
            var keep = new HashSet<string>(items.Select(i => i.file).Concat(items.Where(i => !string.IsNullOrEmpty(i.colored)).Select(i => i.colored)));
            foreach (var f in Directory.GetFiles(OutDir, "*.pdf"))   // a story that left the registry takes its PDF along
                if (!keep.Contains(Path.GetFileName(f))) { File.Delete(f); if (File.Exists(f + ".meta")) File.Delete(f + ".meta"); }

            string json = JsonUtility.ToJson(new Index { sheets = items.ToArray() }, true);
            if (!File.Exists(IndexPath) || File.ReadAllText(IndexPath) != json) File.WriteAllText(IndexPath, json);
            AssetDatabase.Refresh();
            Debug.Log($"Sheet PDFs bundled: {string.Join(", ", items.Select(i => string.IsNullOrEmpty(i.colored) ? i.book + " (blank only)" : i.book))}");
        }
    }
}
