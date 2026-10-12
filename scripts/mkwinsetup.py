#!/usr/bin/env python3
"""Append the real installer to the setup window program.

usage: mkwinsetup.py <setup-ui.exe> <mini_installer.exe> <output.exe>

Layout: [setup-ui.exe][installer payload][u64 little-endian payload size]["JBPAYLD1"]
(the setup window finds the payload from the end of its own file).
"""
import shutil
import struct
import sys

stub, payload, out = sys.argv[1:4]
size = 0
with open(out, "wb") as o:
    with open(stub, "rb") as f:
        shutil.copyfileobj(f, o)
    with open(payload, "rb") as f:
        shutil.copyfileobj(f, o, 1 << 20)
        size = f.tell()
    o.write(struct.pack("<Q", size) + b"JBPAYLD1")
print(f"wrote {out}: stub + {size} byte payload")
