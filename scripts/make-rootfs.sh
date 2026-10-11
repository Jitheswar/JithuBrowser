#!/usr/bin/env bash
# One-time: create an Ubuntu 22.04 rootfs under build-work/rootfs for building on
# hosts whose glibc is older than 2.34 (e.g. RHEL 8). Needs unprivileged user
# namespaces. Not needed on Ubuntu 22.04+/Debian 12+/Fedora.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build-work/rootfs
[ -f build-work/ubuntu-base.tgz ] || curl -fL https://cdimage.ubuntu.com/ubuntu-base/releases/22.04/release/ubuntu-base-22.04-base-amd64.tar.gz -o build-work/ubuntu-base.tgz
tar -xzf build-work/ubuntu-base.tgz -C build-work/rootfs --exclude='dev/*'
scripts/enter-rootfs.sh bash -c '
  export DEBIAN_FRONTEND=noninteractive
  echo "APT::Sandbox::User \"root\";" > /etc/apt/apt.conf.d/99nosandbox
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends git gperf bison flex pkg-config python3 ca-certificates curl xz-utils file perl lsb-release libnss3 libnspr4 libglib2.0-0 libx11-6 libxcb1 libfontconfig1 libfreetype6 libxkbcommon0 libgbm1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libpango-1.0-0 libcairo2 libxext6 libatspi2.0-0 libdrm2 libgtk-3-0 fonts-liberation xvfb openbox xdotool x11-utils||true
  printf "#!/bin/sh\nexit 0\n" > /var/lib/dpkg/info/dbus.postinst; dpkg --configure -a || true'
echo "rootfs ready"
