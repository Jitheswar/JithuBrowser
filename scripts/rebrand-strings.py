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
FILES = [
    "chrome/app/chromium_strings.grd",
    "chrome/app/settings_chromium_strings.grdp",
    "components/components_chromium_strings.grd",
    "extensions/strings/extensions_chromium_strings.grdp",
]
# "Chromium" as a standalone word: not part of a URL/domain/path/identifier, not "Chromium OS".
WORD = re.compile(r"(?<![\w./@_:-])Chromium(?![\w@_/-])(?!\.\w)(?! OS)")
total = 0
for rel in FILES:
    path = os.path.join(src, rel)
    text = open(path, encoding="utf-8").read()
    new, n = WORD.subn("JithuBrowser", text)
    if n:
        open(path, "w", encoding="utf-8").write(new)
    total += n
    print(f"{rel}: {n} replacements")
print(f"rebranded {total} strings")
