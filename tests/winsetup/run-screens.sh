#!/usr/bin/env bash
# Runs a setup bundle under Wine on a virtual display and saves framebuffer snapshots (XWD)
# at the given seconds. Run inside the build rootfs:
#   scripts/enter-rootfs.sh bash tests/winsetup/run-screens.sh <bundle.exe> <outdir> <seconds...> [-- installer args]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXE="$1"; OUT="$2"; shift 2
SECS=(); ARGS=()
while [ $# -gt 0 ]; do [ "$1" = "--" ] && { shift; ARGS=("$@"); break; }; SECS+=("$1"); shift; done
mkdir -p "$OUT/fb"
D=:$((120 + RANDOM % 60))
Xvfb "$D" -screen 0 1920x1080x24 -nolisten tcp -fbdir "$OUT/fb" >/dev/null 2>&1 &
XV=$!; trap 'kill $XV 2>/dev/null || true' EXIT
sleep 1
export DISPLAY="$D" WINEPREFIX="${WINEPREFIX:-$HOME/.jithu-wineprefix}" WINEARCH=win64 WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
"$ROOT/build-work/wine11/bin/wine" "$EXE" "${ARGS[@]}" &
WP=$!
t0=$(date +%s)
for s in "${SECS[@]}"; do
  while [ $(( $(date +%s) - t0 )) -lt "$s" ]; do sleep 0.2; done
  cp "$OUT/fb/Xvfb_screen0" "$OUT/at-$s.xwd"
done
wait $WP && echo "exit=0" || echo "exit=$?"
