#!/usr/bin/env bash
# Run the privacy tests against a browser binary on a virtual X display with a
# window manager (so tab switching / minimising really hide windows).
#   tests/run-tests.sh /path/to/chrome            # on a host with Xvfb + openbox
#   JB_ROOTFS_RUN=1 tests/run-tests.sh <chrome>   # inside the build rootfs (see scripts/enter-rootfs.sh)
set -euo pipefail
BROWSER="${1:?usage: run-tests.sh /path/to/browser [pytest args]}"; shift || true
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${JB_PYTHON:-$ROOT/build-work/venv/bin/python}"
if [ -z "${JB_ROOTFS_RUN:-}" ] && [ "${JB_USE_ROOTFS:-0}" = 1 ]; then
  exec "$ROOT/scripts/enter-rootfs.sh" env JB_ROOTFS_RUN=1 "JB_PYTHON=$PY" bash "$ROOT/tests/run-tests.sh" "$BROWSER" "$@"
fi
D=:$((90 + RANDOM % 9))
Xvfb "$D" -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 &
XV=$!; trap 'kill $XV $WM 2>/dev/null || true' EXIT
sleep 1
DISPLAY=$D openbox >/dev/null 2>&1 &
WM=$!; sleep 1
DISPLAY=$D JITHU_BROWSER="$BROWSER" "$PY" -m pytest -v "$ROOT/tests/test_privacy.py" "$@"
