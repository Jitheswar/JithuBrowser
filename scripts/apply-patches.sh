#!/usr/bin/env bash
# Apply patches/series to the Chromium checkout. Resets the main repo and the
# v8 / devtools-frontend sub-repos first unless --no-reset is given.
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$JB_SRC"
if [ "${1:-}" != "--no-reset" ]; then
  for repo in . v8 third_party/devtools-frontend/src third_party/angle; do
    git -C "$repo" checkout -q -- .
    git -C "$repo" clean -qfd -e out/ -e '*.pyc' -- $( [ "$repo" = . ] && echo chrome components content third_party/blink extensions services ui net || echo . )
  done
fi
while read -r p; do
  case "$p" in ''|'#'*) continue ;; esac
  echo "applying $p"
  patch -p1 --forward --no-backup-if-mismatch -s -i "$JB_ROOT/patches/$p"
done < "$JB_ROOT/patches/series"
"$JB_ROOT/scripts/branding.sh"
echo "all patches applied"
