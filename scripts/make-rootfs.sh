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
  apt-get install -y -qq --no-install-recommends git gperf bison flex pkg-config python3 ca-certificates curl xz-utils file perl lsb-release'
echo "rootfs ready"
