#!/bin/bash
# Build JithuBrowser on a Slurm compute node (whole node).
#SBATCH -J jithu-build
#SBATCH -p cluster1-cpu
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH -o build-work/logs/build-%j.log
set -euo pipefail
# Compute nodes have no system git; some build actions (ANGLE/Dawn commit ids) need it.
command -v git >/dev/null || export PATH="$HOME/.local/opt/nodegit/bin:$PATH"
cd "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}"
# Prebuilt Rust bindgen needs GLIBCXX_3.4.26, newer than RHEL 8's system
# libstdc++. The build overrides LD_LIBRARY_PATH with the clang lib dir, so
# drop a newer libstdc++ there.
GCC_LIB="${GCC_LIB:-/opt/ohpc/pub/compiler/gcc/9.3.0/lib64}"
CLANG_LIB="$PWD/build-work/chromium/src/third_party/llvm-build/Release+Asserts/lib"
if ! strings /lib64/libstdc++.so.6 | grep -q GLIBCXX_3.4.26 && [ -e "$GCC_LIB/libstdc++.so.6" ]; then
  ln -sf "$GCC_LIB/libstdc++.so.6" "$CLANG_LIB/libstdc++.so.6"
fi
export JB_JOBS="${JB_JOBS:-$(nproc)}"
./scripts/build.sh
echo BUILD_DONE
