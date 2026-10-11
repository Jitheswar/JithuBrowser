#!/usr/bin/env bash
# Package a finished Linux build as .tar.xz, .deb and .rpm into dist/.
# Works on any distro: .deb is assembled with python (no dpkg needed),
# .rpm needs rpmbuild (skipped with a warning if missing).
set -euo pipefail
source "$(dirname "$0")/env.sh"
OUT="$JB_SRC/$JB_OUT"
DIST="$JB_ROOT/dist"
VER="$JB_CHROMIUM_VERSION.$JB_REVISION"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/root/opt/jithubrowser"
mkdir -p "$APP" "$DIST"

# --- application files -----------------------------------------------------
cp "$OUT/chrome" "$APP/jithubrowser"
cp "$OUT/chrome_sandbox" "$APP/chrome-sandbox"
for f in chrome_crashpad_handler chrome_100_percent.pak chrome_200_percent.pak resources.pak \
         icudtl.dat v8_context_snapshot.bin snapshot_blob.bin libEGL.so libGLESv2.so \
         libvk_swiftshader.so vk_swiftshader_icd.json libvulkan.so.1 libqt5_shim.so libqt6_shim.so \
         chromedriver; do
  [ -e "$OUT/$f" ] && cp -a "$OUT/$f" "$APP/"
done
for d in locales MEIPreload PrivacySandboxAttestationsPreloaded WidevineCdm; do
  [ -d "$OUT/$d" ] && cp -a "$OUT/$d" "$APP/"
done
[ -f "$APP/chromedriver" ] && mv "$APP/chromedriver" "$APP/jithubrowserdriver"
strip --strip-unneeded "$APP/jithubrowser" "$APP"/*.so* 2>/dev/null || true
cp "$JB_ROOT/LICENSE" "$APP/LICENSE.JithuBrowser"
[ -f "$OUT/LICENSE.chromium.html" ] && cp "$OUT/LICENSE.chromium.html" "$APP/" || cp "$JB_SRC/LICENSE" "$APP/LICENSE.chromium"

# Launcher wrapper (used by .deb/.rpm; tarball users run ./jithubrowser directly)
cat > "$APP/jithubrowser-launcher" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export CHROME_WRAPPER="$(readlink -f "$0")"
exec "$HERE/jithubrowser" "$@"
EOF
chmod 755 "$APP/jithubrowser-launcher"

# Desktop integration
R="$STAGE/root"
mkdir -p "$R/usr/bin" "$R/usr/share/applications"
ln -s /opt/jithubrowser/jithubrowser-launcher "$R/usr/bin/jithubrowser"
cp "$JB_ROOT/branding/jithubrowser.desktop" "$R/usr/share/applications/jithubrowser.desktop"
for s in 16 24 32 48 64 128 256; do
  mkdir -p "$R/usr/share/icons/hicolor/${s}x${s}/apps"
  cp "$JB_ROOT/branding/icons/product_logo_$s.png" "$R/usr/share/icons/hicolor/${s}x${s}/apps/jithubrowser.png"
done
mkdir -p "$R/usr/share/icons/hicolor/scalable/apps"
cp "$JB_ROOT/branding/icons/jithubrowser.svg" "$R/usr/share/icons/hicolor/scalable/apps/jithubrowser.svg"

# --- portable tarball --------------------------------------------------------
TARDIR="jithubrowser-$VER-linux-x64"
mkdir -p "$STAGE/tar/$TARDIR"
cp -a "$APP/." "$STAGE/tar/$TARDIR/"
cp "$JB_ROOT/branding/jithubrowser.desktop" "$JB_ROOT/branding/icons/product_logo_256.png" "$STAGE/tar/$TARDIR/"
cat > "$STAGE/tar/$TARDIR/README.txt" <<EOF
JithuBrowser $VER portable build for x86_64 Linux.
Run ./jithubrowser.  If your kernel disallows unprivileged user namespaces, make the
sandbox helper setuid root once:  sudo chown root:root chrome-sandbox && sudo chmod 4755 chrome-sandbox
EOF
tar -C "$STAGE/tar" -cJf "$DIST/$TARDIR.tar.xz" "$TARDIR"
echo "built $DIST/$TARDIR.tar.xz"

# --- .deb (Debian, Ubuntu, Mint, Pop!_OS, ...) ------------------------------
INSTALLED_KB=$(du -sk "$R" | cut -f1)
python3 "$JB_ROOT/scripts/mkdeb.py" "$R" "$DIST/jithubrowser_${VER}_amd64.deb" <<EOF
Package: jithubrowser
Version: $VER
Architecture: amd64
Maintainer: Jitheswar <jitheswaredu@gmail.com>
Installed-Size: $INSTALLED_KB
Depends: libasound2 | libasound2t64, libatk-bridge2.0-0 | libatk-bridge2.0-0t64, libatk1.0-0 | libatk1.0-0t64, libatspi2.0-0 | libatspi2.0-0t64, libc6 (>= 2.28), libcairo2, libcups2 | libcups2t64, libdbus-1-3, libdrm2, libexpat1, libgbm1, libglib2.0-0 | libglib2.0-0t64, libgtk-3-0 | libgtk-3-0t64, libnspr4, libnss3 (>= 3.26), libpango-1.0-0, libx11-6, libxcb1, libxcomposite1, libxdamage1, libxext6, libxfixes3, libxkbcommon0, libxrandr2, xdg-utils, ca-certificates, fonts-liberation
Section: web
Priority: optional
Homepage: https://github.com/Jitheswar/JithuBrowser
Description: Privacy-focused web browser based on official Chromium
 JithuBrowser keeps websites from seeing tab switches, window focus, fullscreen,
 DevTools, installed extensions, browser shortcuts and typing rhythm, while
 staying compatible with Chrome-only websites and Chrome Web Store extensions.
EOF
echo "built $DIST/jithubrowser_${VER}_amd64.deb"

# --- .rpm (Fedora, RHEL, Rocky, Alma, CentOS Stream, openSUSE) ---------------
if command -v rpmbuild >/dev/null; then
  RPMTOP="$STAGE/rpm"
  mkdir -p "$RPMTOP"/{BUILD,RPMS,SPECS,BUILDROOT}
  sed -e "s/@VERSION@/$JB_CHROMIUM_VERSION/" -e "s/@RELEASE@/$JB_REVISION/" \
      "$JB_ROOT/packaging/rpm/jithubrowser.spec.in" > "$RPMTOP/SPECS/jithubrowser.spec"
  rpmbuild --quiet -bb --define "_topdir $RPMTOP" --define "jb_root $R" "$RPMTOP/SPECS/jithubrowser.spec"
  cp "$RPMTOP"/RPMS/x86_64/*.rpm "$DIST/"
  echo "built $(ls "$DIST"/*.rpm)"
else
  echo "warning: rpmbuild not found, skipping .rpm" >&2
fi

(cd "$DIST" && sha256sum ./*.tar.xz ./*.deb ./*.rpm 2>/dev/null > SHA256SUMS)
