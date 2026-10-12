#!/usr/bin/env bash
# Like enter-rootfs.sh, but the command runs as an ordinary NON-ROOT user (uid 1000, no capabilities), and the
# rootfs is entered with pivot_root instead of chroot. That lets the browser's own user-namespace sandbox be
# tested (the kernel refuses to create a user namespace from inside a chroot).
#   scripts/enter-rootfs-user.sh <command...>
set -euo pipefail
R="${JB_ROOTFS:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/build-work/rootfs}"
exec unshare --user --map-root-user --mount bash -c '
  set -e
  R="$1"; shift
  mount --make-rprivate /
  mount --rbind "$R" "$R"
  mount --rbind /home "$R/home"
  mount --rbind /proc "$R/proc"
  mount --rbind /dev  "$R/dev"
  mount --bind  /tmp  "$R/tmp"
  cp -f /etc/resolv.conf "$R/etc/resolv.conf" 2>/dev/null || true
  mkdir -p "$R/.oldroot"
  cd "$R"
  pivot_root . .oldroot
  umount -l /.oldroot
  cd /tmp
  FIFO=/tmp/.jb-user-fifo.$$; rm -f "$FIFO"; mkfifo "$FIFO"
  # Second user namespace: uid/gid 1000 inside, mapped to our (fake-root) uid; the process keeps no capabilities.
  unshare --user bash -c "read _ < $FIFO; exec /usr/bin/env -i HOME=/tmp/claude-5716/uh PATH=/usr/local/bin:/usr/bin:/bin TERM=xterm \"\$@\"" _ "$@" &
  CHILD=$!
  sleep 0.5
  echo "1000 0 1" > /proc/$CHILD/uid_map
  echo deny > /proc/$CHILD/setgroups
  echo "1000 0 1" > /proc/$CHILD/gid_map
  echo go > "$FIFO"
  wait $CHILD; RC=$?; rm -f "$FIFO"; exit $RC
' _ "$R" "$@"
