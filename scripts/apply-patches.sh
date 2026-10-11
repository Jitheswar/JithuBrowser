#!/usr/bin/env bash
# Apply patches/series to the Chromium checkout (idempotent: resets first).
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$JB_SRC"
if [ "${1:-}" != "--no-reset" ]; then
  git reset -q --hard "refs/tags/$JB_CHROMIUM_VERSION" 2>/dev/null || git reset -q --hard HEAD
  git clean -qfd -e out/ -e '*.pyc' -- chrome components content third_party/blink v8 extensions services ui net
fi
while read -r p; do
  case "$p" in ''|'#'*) continue ;; esac
  echo "applying $p"
  git apply --whitespace=nowarn -p1 "$JB_ROOT/patches/$p"
done < "$JB_ROOT/patches/series"
"$JB_ROOT/scripts/branding.sh"
echo "all patches applied"
