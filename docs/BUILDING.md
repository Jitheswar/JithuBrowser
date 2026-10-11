# Building JithuBrowser

JithuBrowser is official Chromium (tag in `CHROMIUM_VERSION`) plus the patches in `patches/`.
Most people should download a release instead; building needs ~100-150 GB of disk, 16-32 GB of RAM and hours of CPU.

## Linux

```bash
./scripts/fetch.sh            # depot_tools + shallow Chromium checkout in build-work/
./scripts/apply-patches.sh    # reset, apply patches/series, rebrand
./scripts/build.sh            # gn gen + autoninja   (JB_JOBS=<n> to limit parallelism)
./scripts/package-linux.sh    # dist/*.tar.xz, *.deb, *.rpm
```

On an HPC/Slurm cluster build on a compute node: `sbatch scripts/slurm/build.sbatch`.
Compute nodes need `git` (the build calls it); on hosts with glibc/libstdc++ older than Chromium's prebuilt Rust tools expect (RHEL 8), `build.sbatch` links a newer `libstdc++` into the clang lib directory.

## Windows

Run on Windows 10/11 with Visual Studio 2022 (C++ + MFC/ATL + Windows SDK + debugging tools):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\build.ps1
powershell -ExecutionPolicy Bypass -File scripts\windows\package.ps1   # needs Inno Setup 6 for the installer
```

Google's hosted Windows toolchain is internal-only, so the script sets `DEPOT_TOOLS_WIN_TOOLCHAIN=0`.
Cross-compiling for Windows from Linux is not supported by this repo.

## Changing a patch

Edit files in `build-work/chromium/src`, then `scripts/export-patch.sh NNNN-name.patch <paths...>`.
