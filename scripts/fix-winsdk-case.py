#!/usr/bin/env python3
"""Make the Windows SDK / MSVC headers usable from a case-sensitive Linux filesystem.

Windows headers are looked up case-insensitively, so Chromium and its third-party code write
#include <ObjBase.h> for the file objbase.h. Chromium's own cross-build recipe mounts the SDK on a
case-insensitive FUSE filesystem (ciopfs); that is not available everywhere (e.g. unprivileged
HPC nodes), so instead this script scans every #include in the source tree and adds a symlink with
the requested spelling next to each SDK header whose real name differs only by case.

usage: fix-winsdk-case.py <winsysroot> <chromium src dir>
"""
import os
import re
import subprocess
import sys

winsys, src = map(os.path.abspath, sys.argv[1:3])
kits = os.path.join(winsys, "Windows Kits", "10", "Include")
sdk = next(os.path.join(kits, d) for d in sorted(os.listdir(kits)) if re.fullmatch(r"10\.0\.\d+", d))
msvc = os.path.join(winsys, "VC", "Tools", "MSVC")
msvc = os.path.join(msvc, sorted(os.listdir(msvc))[-1], "include")
roots = [os.path.join(sdk, d) for d in ("ucrt", "shared", "um", "winrt", "cppwinrt")] + [msvc]


def index(root):
    idx = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for n in filenames + dirnames:
            full = os.path.join(dirpath, n)
            idx.setdefault(os.path.relpath(full, root).lower(), os.path.relpath(full, root))
    return idx


indexes = {r: index(r) for r in roots}

# Every include spelled anywhere in the Chromium tree (generated build dirs and node_modules excluded).
cmd = ["grep", "-rhoIE", "--include=*.h", "--include=*.hpp", "--include=*.hh", "--include=*.cc", "--include=*.cpp",
       "--include=*.cxx", "--include=*.c", "--include=*.inc", "--include=*.inl", "--exclude-dir=out", "--exclude-dir=node_modules",
       "--exclude-dir=.git", "--exclude-dir=llvm-build", "--exclude-dir=rust-toolchain", "--exclude-dir=sysroot",
       r'^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"][^>"]+[>"]', src]
out = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout
names = set()
for line in out.splitlines():
    m = re.search(r'[<"]([^>"]+)[>"]', line)
    if m:
        names.add(m.group(1).replace("\\", "/"))

made = skipped = 0
for name in sorted(names):
    if any(os.path.exists(os.path.join(r, name)) for r in roots):
        continue
    low = name.lower()
    for r in roots:
        real = indexes[r].get(low)
        if not real:
            continue
        link = os.path.join(r, name)
        os.makedirs(os.path.dirname(link), exist_ok=True)
        if os.path.lexists(link):
            skipped += 1
            break
        os.symlink(os.path.relpath(os.path.join(r, real), os.path.dirname(link)), link)
        made += 1
        break
print(f"scanned {len(names)} distinct includes; created {made} case symlinks ({skipped} already present)")
