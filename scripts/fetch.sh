#!/usr/bin/env bash
# Fetch official Chromium at the pinned tag using Google's depot_tools.
set -euo pipefail
source "$(dirname "$0")/env.sh"
mkdir -p "$JB_WORK/chromium"
[ -d "$JB_WORK/depot_tools" ] || git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git "$JB_WORK/depot_tools"
cd "$JB_WORK/chromium"
if [ ! -f .gclient ]; then
  cat > .gclient <<'GCLIENT'
solutions = [{
  "name": "src",
  "url": "https://chromium.googlesource.com/chromium/src.git",
  "managed": False,
  "custom_deps": {},
  "custom_vars": {"checkout_nacl": False, "checkout_pgo_profiles": True},
}]
GCLIENT
  # target_os is appended by the caller for Windows builds (see scripts/windows/build.ps1).
  echo "target_os = [\"${JB_TARGET_OS:-linux}\"]" >> .gclient
fi
gclient sync --no-history --shallow --nohooks -j "${JB_JOBS:-8}" --revision "src@refs/tags/$JB_CHROMIUM_VERSION"
gclient runhooks -j "${JB_JOBS:-8}"
