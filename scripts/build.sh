#!/usr/bin/env bash
# Configure and build JBrowser.  JB_JOBS controls ninja parallelism.
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$JB_SRC"
mkdir -p "$JB_OUT"
cp "$JB_ROOT/args.gn" "$JB_OUT/args.gn"
[ -n "${JB_EXTRA_ARGS:-}" ] && echo "$JB_EXTRA_ARGS" >> "$JB_OUT/args.gn"
gn gen "$JB_OUT"
autoninja -C "$JB_OUT" -j "${JB_JOBS:-$(nproc)}" chrome chrome_sandbox chromedriver ${JB_EXTRA_TARGETS:-}
