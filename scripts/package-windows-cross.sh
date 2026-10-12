#!/usr/bin/env bash
# Collect the cross-compiled Windows installer into dist/ (run after scripts/build-windows.sh).
# mini_installer.exe is Chromium's self-contained installer (setup.exe + the browser archive); it is
# shipped inside the animated setup window built by scripts/build-windows-setup.sh.
set -euo pipefail
source "$(dirname "$0")/env.sh"
OUT="$JB_SRC/out/JithuBrowser-win"
VER="$JB_CHROMIUM_VERSION.$JB_REVISION"
DIST="$JB_ROOT/dist"
mkdir -p "$DIST"
[ -f "$OUT/mini_installer.exe" ] || { echo "missing $OUT/mini_installer.exe: build first" >&2; exit 1; }
DEST="$DIST/JithuBrowser-$VER-windows-x64-installer.exe"
# Wrap Chromium's silent installer in a setup window with an animated progress display
# (packaging/windows/setup-ui). The wrapper runs the real installer unchanged; /silent skips the window.
"$JB_ROOT/scripts/enter-rootfs.sh" bash "$JB_ROOT/scripts/build-windows-setup.sh" >/dev/null
python3 "$JB_ROOT/scripts/mkwinsetup.py" "$JB_WORK/setup-ui/setup-ui.exe" "$OUT/mini_installer.exe" "$DEST"
file "$DEST" 2>/dev/null | cut -c1-160 || true
(cd "$DIST" && sha256sum "$(basename "$DEST")" > SHA256SUMS-windows.txt)
cat "$DIST/SHA256SUMS-windows.txt"
echo "NOTE: cross-compiled on Linux; it has not been run on Windows. Label it untested."
