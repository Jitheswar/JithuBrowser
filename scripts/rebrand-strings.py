#!/usr/bin/env python3
"""Rebrand the English UI strings: "Chromium" -> "JithuBrowser".

Chromium's menus, About page, settings and installer text come from grit string sources
(chromium_strings.grd and friends). BRANDING only changes version metadata, so without this the
browser still greets users as "Chromium". The script is idempotent and conservative: it does not
touch URLs/domains (chromium.org), identifiers (name="IDS_..."), file names, or "Chromium OS".

Translations are keyed by a hash of the English text, so changed messages fall back to English in
other languages until they are translated. usage: rebrand-strings.py <chromium src dir>
"""
import os
import re
import sys

src = sys.argv[1]
ROOTS = ["chrome", "components", "extensions", "content", "ui", "services"]
SKIP = ("/ios", "/android", "/chromeos", "/ash/", "/test", "/tests/", "google_chrome", "/out/", "node_modules", "/third_party/")


def string_sources():
    for root in ROOTS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(src, root)):
            dirnames[:] = [d for d in dirnames if d not in ("out", "node_modules", "third_party", ".git")]
            for f in filenames:
                if f.endswith((".grd", ".grdp")):
                    path = os.path.join(dirpath, f)
                    rel = os.path.relpath(path, src)
                    if not any(k in "/" + rel for k in SKIP):
                        yield rel
# "Chromium" as a standalone word: not part of a URL/domain/path/identifier, not "Chromium OS".
WORD = re.compile(r"(?<![\w./@_:-])Chromium(?![\w@_/-])(?!\.\w)(?! OS)")
total = 0
for rel in sorted(string_sources()):
    path = os.path.join(src, rel)
    text = open(path, encoding="utf-8").read()
    new, n = WORD.subn("JithuBrowser", text)
    if n:
        open(path, "w", encoding="utf-8").write(new)
    total += n
    if n:
        print(f"{rel}: {n} replacements")
print(f"rebranded {total} strings")
