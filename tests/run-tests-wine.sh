#!/usr/bin/env bash
# Run the privacy tests against a Windows build under Wine: a smoke test of a cross-compiled
# .exe on a machine without Windows. Needs Wine >= 10 (WoW64 build), Xvfb and openbox.
#   tests/run-tests-wine.sh /path/to/wine /path/to/out/JithuBrowser-win [pytest args]
# Inside the build rootfs:  scripts/enter-rootfs.sh bash tests/run-tests-wine.sh ...
set -euo pipefail
export JB_WINE="${1:?usage: run-tests-wine.sh /path/to/wine /path/to/out/dir [pytest args]}"
export JB_WINE_OUTDIR="${2:?}"
shift 2
export WINEPREFIX="${WINEPREFIX:-$HOME/.jithu-wineprefix}" WINEARCH=win64 WINEDEBUG=-all
export WINEDLLOVERRIDES="mscoree,mshtml="

WRAPPER="$(mktemp -d)/chrome-wine"
cat > "$WRAPPER" <<'WRAP'
#!/usr/bin/env bash
# Translate unix paths in --user-data-dir to Wine's Z: drive, then run the Windows chrome.exe.
args=()
for a in "$@"; do
  case "$a" in
    --user-data-dir=*) p="${a#*=}"; a="--user-data-dir=Z:${p//\//\\}" ;;
  esac
  args+=("$a")
done
cd "$JB_WINE_OUTDIR"
exec "$JB_WINE" ./chrome.exe "${args[@]}"
WRAP
chmod +x "$WRAPPER"

# Attach over the DevTools port: Playwright's pipe transport cannot cross the wrapper/Wine.
JITHU_CDP_ONLY=1 "$(dirname "${BASH_SOURCE[0]}")/run-tests.sh" "$WRAPPER" "$@"
