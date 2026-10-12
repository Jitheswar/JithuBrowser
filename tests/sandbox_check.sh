#!/usr/bin/env bash
# Checks that the browser's own sandbox is really engaged when it is started WITHOUT --no-sandbox.
# Run as a NON-ROOT user, e.g.:  scripts/enter-rootfs-user.sh bash tests/sandbox_check.sh /path/to/browser
B="${1:?usage: sandbox_check.sh /path/to/browser}"
$B --headless=new --disable-gpu --no-first-run --user-data-dir=$(mktemp -d) --remote-debugging-port=9461 "data:text/html,<title>t</title>hello" >/dev/null 2>&1 &
BP=$!; sleep 8
echo "browser started WITHOUT --no-sandbox; processes of THIS run (renderers should show Seccomp: 2, NoNewPrivs: 1):"
for pid in $(ls /proc | grep -E '^[0-9]+$'); do
  c=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null) || continue
  case "$c" in *"user-data-dir=$(mktemp -d)"*)
    t=$(echo "$c" | grep -o -E -- '--type=[a-z-]+' | head -1); t=${t:-browser}
    echo "  $t pid=$pid  $(grep -E '^(Seccomp|NoNewPrivs):' /proc/$pid/status 2>/dev/null | tr '\n\t' '  ')  userns=$(readlink /proc/$pid/ns/user 2>/dev/null)";;
  esac
done | sort -u
echo "  (browser's own ns: $(readlink /proc/$BP/ns/user))"
kill $BP 2>/dev/null
