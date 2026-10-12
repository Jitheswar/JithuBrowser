#!/usr/bin/env python3
"""Build a .deb without dpkg: mkdeb.py <rootdir> <out.deb>  (control file on stdin).

A .deb is an `ar` archive of debian-binary, control.tar.xz and data.tar.xz.
All files are owned by root; chrome-sandbox is installed setuid (4755).
"""
import io
import os
import sys
import tarfile
import time

POSTINST = """#!/bin/sh
set -e
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
if command -v update-alternatives >/dev/null; then
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/jithubrowser 120 || true
fi
"""
PRERM = """#!/bin/sh
set -e
if [ "$1" = remove ] && command -v update-alternatives >/dev/null; then
  update-alternatives --remove x-www-browser /usr/bin/jithubrowser || true
fi
"""


def root_owned(ti):
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = "root"
    if ti.name.endswith("/chrome-sandbox"):
        ti.mode = 0o4755
    return ti


def tar_xz(add):
    buf = io.BytesIO()
    # GNU format: dpkg's own tar reader rejects the PAX extended headers (type 'x') that Python writes by default.
    with tarfile.open(fileobj=buf, mode="w:xz", preset=6, format=tarfile.GNU_FORMAT) as t:
        add(t)
    return buf.getvalue()


def add_bytes(t, name, data, mode):
    ti = tarfile.TarInfo(name)
    ti.size, ti.mode, ti.mtime = len(data), mode, int(time.time())
    t.addfile(root_owned(ti), io.BytesIO(data))


def ar_member(name, data):
    hdr = f"{name:<16}{int(time.time()):<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n".encode()
    return hdr + data + (b"\n" if len(data) % 2 else b"")


def main():
    root, out = sys.argv[1], sys.argv[2]
    control = sys.stdin.read().strip() + "\n"

    def add_control(t):
        add_bytes(t, "./control", control.encode(), 0o644)
        add_bytes(t, "./postinst", POSTINST.encode(), 0o755)
        add_bytes(t, "./prerm", PRERM.encode(), 0o755)

    def add_data(t):
        for entry in sorted(os.listdir(root)):
            t.add(os.path.join(root, entry), arcname="./" + entry, filter=root_owned)

    with open(out, "wb") as f:
        f.write(b"!<arch>\n")
        f.write(ar_member("debian-binary", b"2.0\n"))
        f.write(ar_member("control.tar.xz", tar_xz(add_control)))
        f.write(ar_member("data.tar.xz", tar_xz(add_data)))


if __name__ == "__main__":
    main()
