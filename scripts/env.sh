# Shared settings for JithuBrowser scripts. Source this file.
JB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JB_WORK="${JB_WORK:-$JB_ROOT/build-work}"           # depot_tools + chromium checkout live here
JB_SRC="$JB_WORK/chromium/src"
JB_FLAVOR="${JB_FLAVOR:-release}"
if [ "$JB_FLAVOR" = dev ]; then JB_OUT="${JB_OUT:-out/JithuBrowser-dev}"; else JB_OUT="${JB_OUT:-out/JithuBrowser}"; fi
JB_CHROMIUM_VERSION="$(cat "$JB_ROOT/CHROMIUM_VERSION")"
JB_REVISION="$(cat "$JB_ROOT/JITHUBROWSER_REVISION")"
JB_VERSION="$JB_CHROMIUM_VERSION-$JB_REVISION"
export PATH="$JB_WORK/depot_tools:$PATH"
export DEPOT_TOOLS_UPDATE=0
