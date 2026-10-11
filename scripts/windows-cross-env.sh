# Source this to cross-compile the Windows build from Linux (target_os = "win").
# Needs scripts/fetch-winsdk.sh to have run (build-work/winsysroot + metadata files).
# Hermetic-toolchain mode (=1) makes Chromium use clang-cl /winsysroot with that directory.
# For `gclient runhooks` use DEPOT_TOOLS_WIN_TOOLCHAIN=0 so it does not try to download
# Google's (non-public) toolchain package.
export DEPOT_TOOLS_WIN_TOOLCHAIN=1
