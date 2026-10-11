#!/usr/bin/env bash
# Developer helper: export the current diff of the given paths (relative to the
# Chromium src dir, or prefixed v8:/devtools:/sub:<repo>: for nested repos) to patches/<name>
# and make sure it is listed in patches/series.
#   scripts/export-patch.sh 0002-hide-visibility.patch third_party/blink/renderer/core/dom/document.cc ...
set -euo pipefail
source "$(dirname "$0")/env.sh"
name="$1"; shift
out="$JB_ROOT/patches/$name"
: > "$out"
for p in "$@"; do
  case "$p" in
    v8:*)       (cd "$JB_SRC/v8" && git diff --src-prefix=a/v8/ --dst-prefix=b/v8/ -- "${p#v8:}") >> "$out" ;;
    devtools:*) (cd "$JB_SRC/third_party/devtools-frontend/src" && git diff --src-prefix=a/third_party/devtools-frontend/src/ --dst-prefix=b/third_party/devtools-frontend/src/ -- "${p#devtools:}") >> "$out" ;;
    sub:*)      # sub:<repo dir relative to src>:<path inside that repo>   (nested DEPS repo, e.g. third_party/angle)
                rest="${p#sub:}"; repo="${rest%%:*}"; file="${rest#*:}"
                (cd "$JB_SRC/$repo" && git diff --src-prefix="a/$repo/" --dst-prefix="b/$repo/" -- "$file") >> "$out" ;;
    *)          (cd "$JB_SRC" && git diff -- "$p") >> "$out" ;;
  esac
done
[ -s "$out" ] || { echo "empty diff for $name" >&2; rm -f "$out"; exit 1; }
grep -qxF "$name" "$JB_ROOT/patches/series" 2>/dev/null || echo "$name" >> "$JB_ROOT/patches/series"
echo "wrote $out ($(grep -c '^diff --git' "$out") files)"
