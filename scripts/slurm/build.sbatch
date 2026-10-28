#!/bin/bash
# Build JithuBrowser on a Slurm compute node (whole node).
#   sbatch scripts/slurm/build.sbatch                  # release build (LTO, slow)
#   JB_FLAVOR=dev sbatch --export=ALL scripts/slurm/build.sbatch   # fast verification build
# Chromium 155's prebuilt Rust tools need glibc >= 2.34 but RHEL 8 has 2.28, so the
# build runs inside an Ubuntu 22.04 rootfs (build-work/rootfs) via user namespaces.
# Create it once with scripts/make-rootfs.sh.
#SBATCH -J jithu-build
#SBATCH -p cluster1-cpu
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH -o build-work/logs/build-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}"
# Deterministic PATH: prebuilt gn + ninja binaries first (depot_tools' "gn"
# and "ninja" are python wrappers that need the prebuilt binaries on PATH),
# then depot_tools (autoninja, cipd, vpython).
export PATH="$PWD/build-work/chromium/src/buildtools/linux64:$PWD/build-work/chromium/src/third_party/ninja:$PWD/build-work/depot_tools:$PATH"
export JB_JOBS="${JB_JOBS:-$(nproc)}"
scripts/enter-rootfs.sh env JB_JOBS="$JB_JOBS" JB_FLAVOR="${JB_FLAVOR:-release}" JB_EXTRA_TARGETS="${JB_EXTRA_TARGETS:-}" \
  bash -c "cd '$PWD' && ./scripts/build.sh"
echo BUILD_DONE
