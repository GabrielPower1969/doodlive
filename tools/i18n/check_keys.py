#!/usr/bin/env python3
"""Fail when Unity code asks for a UI string that tools/i18n/strings.json does not have (LESSONS 2026-11-22).
Only literal keys are checked: L10n.T("key"), L10n.Raw("key"), L10n.In("<lang>", "key"), BiKey(..., "key", ...)."""
import glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
have = set(json.load(open(f"{ROOT}/tools/i18n/strings.json", encoding="utf-8")))
pat = re.compile(r'L10n\.(?:T|Raw|Other)\("([A-Za-z0-9_]+)"[,)]|L10n\.In\("[a-z]+", "([A-Za-z0-9_]+)"\)|BiKey\([^;]*?, "([A-Za-z0-9_]+)",')
missing = set()
for f in glob.glob(f"{ROOT}/unity/Assets/DoodLive/**/*.cs", recursive=True):
    if f.endswith("/L10n.cs"):
        continue
    for m in pat.finditer(open(f, encoding="utf-8").read()):
        k = next(g for g in m.groups() if g)
        if k not in have:
            missing.add((k, os.path.relpath(f, ROOT)))
for k, f in sorted(missing):
    print(f"missing UI string {k!r} (used in {f}): add it to tools/i18n/strings.json, run tools/gen_i18n.py")
sys.exit(1 if missing else 0)
