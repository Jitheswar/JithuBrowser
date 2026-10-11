#!/usr/bin/env bash
# Rebrand the Chromium checkout as JithuBrowser: product names and icons.
# Called by apply-patches.sh; safe to run repeatedly.
set -euo pipefail
source "$(dirname "$0")/env.sh"
T="$JB_SRC/chrome/app/theme/chromium"

sed -i \
  -e 's/^COMPANY_FULLNAME=.*/COMPANY_FULLNAME=JithuBrowser Authors/' \
  -e 's/^COMPANY_SHORTNAME=.*/COMPANY_SHORTNAME=JithuBrowser Authors/' \
  -e 's/^PRODUCT_FULLNAME=.*/PRODUCT_FULLNAME=JithuBrowser/' \
  -e 's/^PRODUCT_SHORTNAME=.*/PRODUCT_SHORTNAME=JithuBrowser/' \
  -e 's/^PRODUCT_INSTALLER_FULLNAME=.*/PRODUCT_INSTALLER_FULLNAME=JithuBrowser Installer/' \
  -e 's/^PRODUCT_INSTALLER_SHORTNAME=.*/PRODUCT_INSTALLER_SHORTNAME=JithuBrowser Installer/' \
  -e 's/^COPYRIGHT=.*/COPYRIGHT=Copyright @LASTCHANGE_YEAR@ JithuBrowser Authors. All rights reserved./' \
  -e 's/^MAC_BUNDLE_ID=.*/MAC_BUNDLE_ID=io.github.jitheswar.JithuBrowser/' \
  "$T/BRANDING"

ICONS="$JB_ROOT/branding/icons"
for s in 16 24 48 64 128 256; do
  [ -f "$T/product_logo_$s.png" ] && cp "$ICONS/product_logo_$s.png" "$T/product_logo_$s.png"
  [ -f "$T/linux/product_logo_$s.png" ] && cp "$ICONS/product_logo_$s.png" "$T/linux/product_logo_$s.png"
done
cp "$ICONS/jithubrowser.ico" "$T/win/chromium.ico"
echo "branding applied"
