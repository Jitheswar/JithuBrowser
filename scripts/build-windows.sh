#!/usr/bin/env bash
# Cross-compile JithuBrowser for Windows x64 from Linux.
# Prereqs: scripts/fetch-winsdk.sh (Microsoft toolchain via xwin) and a checkout
# synced with JB_TARGET_OS="linux win" ./scripts/fetch.sh, patches applied.
set -euo pipefail
source "$(dirname "$0")/env.sh"
source "$JB_ROOT/scripts/windows-cross-env.sh"
# Windows looks headers up case-insensitively; add symlinks for every spelling Chromium uses.
python3 "$JB_ROOT/scripts/fix-winsdk-case.py" "${JB_WINSYSROOT:-$JB_WORK/winsysroot}" "$JB_SRC"
cd "$JB_SRC"
OUT=out/JithuBrowser-win
mkdir -p "$OUT"
cp "$JB_ROOT/args.gn" "$OUT/args.gn"
cat >> "$OUT/args.gn" <<'ARGS'
target_os = "win"
target_cpu = "x64"
use_clang_modules = false
# dxildia (inside Dawn's built DXC) needs dia2.h from Visual Studio's DIA SDK, which the public
# toolchain download does not include. WebGPU then uses the system FXC compiler instead.
dawn_use_built_dxc = false
ARGS
# Linux-only options in the shared args.gn do not apply on Windows; widevine/codecs do.
gn gen "$OUT"
autoninja -C "$OUT" -k "${JB_KEEP_GOING:-1}" -j "${JB_JOBS:-$(nproc)}" chrome chromedriver mini_installer
ls -la "$OUT"/chrome.exe "$OUT"/mini_installer.exe
