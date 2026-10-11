#!/usr/bin/env bash
# Fetch the MSVC CRT + Windows SDK on Linux (no Windows machine needed) so the
# Windows build can be cross-compiled. Uses the open-source `xwin` tool, which
# downloads straight from Microsoft's public Visual Studio channel.
#
# By running this you accept Microsoft's licence terms for the Visual Studio
# Build Tools / Windows SDK: https://go.microsoft.com/fwlink/?LinkId=2086102
# (the script passes --accept-license on your behalf, only when you set
#  JB_ACCEPT_MS_LICENSE=1).
#
# Output: build-work/winsysroot  (clang-cl /winsysroot layout)
# Also writes the two metadata files Chromium's cross-build wiring looks for
# (Windows Kits/10/bin/SetEnv.{x86,x64}.json and src/build/win_toolchain.json)
# and an empty placeholder cl.exe (clang-cl is used; Chromium only locates the dir).
set -euo pipefail
source "$(dirname "$0")/env.sh"
[ "${JB_ACCEPT_MS_LICENSE:-0}" = 1 ] || { echo "Set JB_ACCEPT_MS_LICENSE=1 to accept Microsoft's licence terms (see header)." >&2; exit 1; }

XWIN_VER=0.10.0
# Chromium 155 targets the Visual Studio 2026 toolchain (MSVC 14.5x) and Windows SDK 10.0.28000.
SDK_VER="${JB_WINSDK_VERSION:-10.0.28000}"
MANIFEST="${JB_VS_MANIFEST:-18}"
BIN="$JB_WORK/xwin-bin"
OUT="${JB_WINSYSROOT:-$JB_WORK/winsysroot}"
mkdir -p "$BIN"
if [ ! -x "$BIN/xwin" ]; then
  T="xwin-$XWIN_VER-x86_64-unknown-linux-musl.tar.gz"
  curl -fsSL -o "$BIN/$T" "https://github.com/Jake-Shadle/xwin/releases/download/$XWIN_VER/$T"
  echo "$(curl -fsSL "https://github.com/Jake-Shadle/xwin/releases/download/$XWIN_VER/$T.sha256" | cut -d' ' -f1)  $BIN/$T" | sha256sum -c -
  tar -xzf "$BIN/$T" -C "$BIN" --strip-components=1
fi

rm -rf "$OUT"
CACHE="$BIN/cache$MANIFEST"
# Microsoft's VS 2026 manifest contains a literal space in some payload URLs ("w kits2"), which xwin
# does not percent-encode. Fetch the manifests once, fix the URLs, serve the corrected package
# manifest from a throwaway local web server and give xwin a channel file that points at it.
MAN="$BIN/vs$MANIFEST.channel.fixed.json"
if [ ! -f "$MAN" ]; then
  "$BIN/xwin" --accept-license --cache-dir "$CACHE" --manifest-version "$MANIFEST" --arch x86_64 list >/dev/null
  python3 - "$CACHE" "$BIN" "$MANIFEST" <<'PY'
import glob, hashlib, json, sys
cache, bin_, ver = sys.argv[1:]
load = lambda f: json.loads(open(f, "rb").read().decode("utf-8-sig"))
pkg = load(glob.glob(cache + "/dl/pkg_manifest_*.vsman")[0])
def fix(o):
    if isinstance(o, dict):
        for k, v in list(o.items()):
            if k == "url" and isinstance(v, str):
                o[k] = v.replace(" ", "%20")
            else:
                fix(v)
    elif isinstance(o, list):
        for v in o:
            fix(v)
fix(pkg)
data = json.dumps(pkg).encode()
open(f"{bin_}/vs{ver}.pkg.vsman", "wb").write(data)
ch = load(cache + f"/dl/manifest_{ver}.json")
p = next(i for i in ch["channelItems"] if i["id"] == "Microsoft.VisualStudio.Manifests.VisualStudio")["payloads"][0]
p["url"] = f"http://127.0.0.1:8765/vs{ver}.pkg.vsman"
p["sha256"] = hashlib.sha256(data).hexdigest()
p["size"] = len(data)
json.dump(ch, open(f"{bin_}/vs{ver}.channel.fixed.json", "w"))
PY
fi
(cd "$BIN" && python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$BIN/httpd.pid")
trap 'kill $(cat "$BIN/httpd.pid") 2>/dev/null || true' EXIT
sleep 1
"$BIN/xwin" --accept-license --cache-dir "$CACHE" --manifest "$MAN" --arch x86,x86_64 --variant desktop --include-atl --sdk-version "$SDK_VER" \
  splat --use-winsysroot-style --preserve-ms-arch-notation --output "$OUT"

MSVC="$(basename "$(ls -d "$OUT"/VC/Tools/MSVC/14.*)")"
KITS="$OUT/Windows Kits/10"
# Chromium names the SDK directory with a 4th component.
ln -sfn "$SDK_VER" "$KITS/Include/$SDK_VER.0"
ln -sfn "$SDK_VER" "$KITS/Lib/$SDK_VER.0"
for a in x64 x86; do
  mkdir -p "$OUT/VC/Tools/MSVC/$MSVC/bin/Hostx64/$a"
  : > "$OUT/VC/Tools/MSVC/$MSVC/bin/Hostx64/$a/cl.exe"
done

mkdir -p "$KITS/bin"
python3 - "$OUT" "$MSVC" "$SDK_VER.0" "$KITS" <<'EOF'
import json, os, sys
out, msvc, sdk, kits = sys.argv[1:]
def env(cpu):
    m = ["VC", "Tools", "MSVC", msvc]
    k = ["Windows Kits", "10"]
    return {"env": {
        "VSINSTALLDIR": [["."]],
        "INCLUDE": [m + ["include"]] + [k + ["Include", sdk, d] for d in ("ucrt", "shared", "um", "winrt", "cppwinrt")],
        "LIB": [m + ["lib", cpu]] + [k + ["Lib", sdk, d, cpu] for d in ("ucrt", "um")],
        "LIBPATH": [m + ["lib", cpu]],
        "PATH": [m + ["bin", "Hostx64", cpu]],
    }}
for cpu in ("x86", "x64"):
    json.dump(env(cpu), open(os.path.join(kits, "bin", f"SetEnv.{cpu}.json"), "w"), indent=1)
EOF

# Chromium reads this file when DEPOT_TOOLS_WIN_TOOLCHAIN=1 (hermetic-toolchain mode).
# runtime_dirs is empty: the redistributable VC runtime DLLs are not fetched (release builds
# link the CRT statically); verify with scripts/check-win-imports.sh after building.
python3 - "$OUT" "$KITS" "$JB_SRC/build/win_toolchain.json" <<'EOF'
import json, sys
out, kits, dest = sys.argv[1:]
json.dump({"path": out, "version": "2026", "win_sdk": kits, "wdk": "", "runtime_dirs": []}, open(dest, "w"), indent=1)
EOF
echo "Windows toolchain ready: $OUT (MSVC $MSVC, SDK $SDK_VER)"
