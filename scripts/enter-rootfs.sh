#!/usr/bin/env bash
# Run a command inside the Ubuntu 22.04 rootfs (glibc 2.35) without root, using
# a user+mount namespace. /home is bind-mounted so the source tree is shared.
# usage: enter-rootfs.sh <command...>
set -euo pipefail
R="${JB_ROOTFS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/build-work/rootfs}"
exec unshare --user --map-root-user --mount bash -c '
  set -e
  R="$1"; shift
  mount --rbind /home "$R/home"
  mount --rbind /proc "$R/proc"
  mount --rbind /dev  "$R/dev"
  mount --bind  /tmp  "$R/tmp"
  [ -d /opt/ohpc ] && { mkdir -p "$R/opt/ohpc"; mount --rbind /opt/ohpc "$R/opt/ohpc"; } || true
  cp -f /etc/resolv.conf "$R/etc/resolv.conf" 2>/dev/null || true
  exec chroot "$R" /usr/bin/env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin TERM=xterm "$@"
' _ "$R" "$@"
