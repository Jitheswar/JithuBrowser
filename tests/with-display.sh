#!/usr/bin/env bash
# Run a command on a virtual X display with a window manager (Xvfb + openbox).
#   tests/with-display.sh <command...>      (inside the rootfs if the host lacks Xvfb/openbox)
set -euo pipefail
D=:$((100 + RANDOM % 80))
Xvfb "$D" -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 &
XV=$!; trap 'kill $XV $WM 2>/dev/null || true' EXIT
sleep 1
DISPLAY=$D openbox >/dev/null 2>&1 &
WM=$!; sleep 1
DISPLAY=$D "$@"
