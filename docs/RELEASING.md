# Releasing prebuilt packages

End users never compile Chromium; they download packages from GitHub Releases.
A release is built from a tagged commit with the pinned Chromium (`CHROMIUM_VERSION`) plus `patches/`.

## 1. Build

```bash
JB_TARGET_OS="linux win" ./scripts/fetch.sh     # once; add "win" only if you cross-compile Windows
./scripts/apply-patches.sh                      # reset + patches + branding
sbatch scripts/slurm/build.sbatch               # Linux release (LTO), or ./scripts/build.sh directly
sbatch scripts/slurm/build-windows.sbatch       # Windows x64 cross-build (needs scripts/fetch-winsdk.sh)
```

## 2. Test before publishing

```bash
JB_USE_ROOTFS=1 tests/run-tests.sh build-work/chromium/src/out/JithuBrowser/chrome   # all tests must pass
```

The privacy tests also run against stock Chrome as a control: the leak tests must fail there.

## 3. Package

```bash
./scripts/package-linux.sh        # dist/: .tar.xz, .deb, .rpm, SHA256SUMS
```

Windows (cross-built): copy `mini_installer.exe` and zip the `chrome.exe` directory into `dist/`.
A cross-built Windows package cannot be run on Linux, so label it **untested** until it has been run on Windows.

## 4. Publish

```bash
git tag v155.0.8059.39.1 && git push origin v155.0.8059.39.1
gh release create v155.0.8059.39.1 dist/* --title "JithuBrowser 155.0.8059.39.1" --notes-file RELEASE_NOTES.md
```

Release notes must say which Chromium version the build is based on, what was tested, and anything untested.
Bump `JITHUBROWSER_REVISION` for each rebuild of the same Chromium version, and rebase the patches when `CHROMIUM_VERSION` changes.
