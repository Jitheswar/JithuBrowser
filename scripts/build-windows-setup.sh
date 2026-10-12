#!/usr/bin/env bash
# Build the small "JithuBrowser Setup" window (packaging/windows/setup-ui) that wraps
# Chromium's mini_installer.exe with an animated progress display. Cross-compiles with the
# same clang-cl + Windows SDK sysroot as the browser. Output: build-work/setup-ui/setup-ui.exe
set -euo pipefail
source "$(dirname "$0")/env.sh"
SRCDIR="$JB_ROOT/packaging/windows/setup-ui"
OUT="$JB_WORK/setup-ui"
SYS="$JB_WORK/winsysroot"
BIN="$JB_SRC/third_party/llvm-build/Release+Asserts/bin"
RC_PY="$JB_SRC/build/toolchain/win/rc/rc.py"
ICON="$JB_SRC/chrome/app/theme/chromium/win/chromium.ico"
[ -d "$SYS" ] || { echo "missing $SYS: run scripts/fetch-winsdk.sh" >&2; exit 1; }
mkdir -p "$OUT"
cp "$SRCDIR"/setup.cc "$SRCDIR"/setup.rc "$SRCDIR"/setup.manifest "$OUT/"
cp "$ICON" "$OUT/jithubrowser.ico"
SDK="$(ls -d "$SYS/Windows Kits/10/Include/10.0."*/ | sort | tail -1)"; SDK="${SDK%/}"; SDKVER="$(basename "$SDK")"
MSVC="$(ls -d "$SYS/VC/Tools/MSVC/"*/ | sort | tail -1)"; MSVC="${MSVC%/}"
( cd "$OUT" && python3 "$RC_PY" /nologo -I. /winsysroot"$SYS" /fosetup.res setup.rc )
"$BIN/clang-cl" --target=x86_64-pc-windows-msvc /winsysroot "$SYS" -fuse-ld=lld \
  /MT /O2 /std:c++17 /EHsc /W3 -Wno-unknown-pragmas /Fe:"$OUT/setup-ui.exe" "$OUT/setup.cc" "$OUT/setup.res" \
  /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup kernel32.lib user32.lib gdi32.lib gdiplus.lib shell32.lib ole32.lib
ls -la "$OUT/setup-ui.exe"
