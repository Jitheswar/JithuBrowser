#!/bin/bash
# Cross-compile the Windows x64 build of JithuBrowser on Linux (Slurm compute node).
# Needs: scripts/fetch-winsdk.sh run once, and the checkout synced with JB_TARGET_OS="linux win".
# Runs inside the Ubuntu rootfs like the Linux build (see scripts/make-rootfs.sh).
#   sbatch scripts/slurm/build-windows.sbatch
#SBATCH -J jithu-win
#SBATCH -p cluster1-cpu
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH -o build-work/logs/build-win-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}"
scripts/enter-rootfs.sh env JB_JOBS="${JB_JOBS:-$(nproc)}" bash -c "cd '$PWD' && ./scripts/build-windows.sh"
echo BUILD_DONE
