#!/usr/bin/env bash
# Builds a test bundle: the real setup window + a dummy installer. Run inside the build rootfs:
#   scripts/enter-rootfs.sh bash tests/winsetup/make-test-bundle.sh <output dir>
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$1"; mkdir -p "$OUT"
BIN="$ROOT/build-work/chromium/src/third_party/llvm-build/Release+Asserts/bin"
( cd "$OUT" && "$BIN/clang-cl" --target=x86_64-pc-windows-msvc /winsysroot "$ROOT/build-work/winsysroot" -fuse-ld=lld \
    /MT /O1 /Fe:dummy.exe "$ROOT/tests/winsetup/dummy-installer.c" \
    /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup kernel32.lib user32.lib )
python3 "$ROOT/scripts/mkwinsetup.py" "$ROOT/build-work/setup-ui/setup-ui.exe" "$OUT/dummy.exe" "$OUT/JithuSetupTest.exe"
