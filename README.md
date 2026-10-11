# JBrowser

**A privacy-focused browser built on official Chromium.** Websites keep working, including Chrome-only ones, and Chrome Web Store extensions install normally. Pages just can't watch what you do.

> Status: **work in progress.** The patch set and build pipeline are under active development; see [ROADMAP](docs/ROADMAP.md).

## What JBrowser hides from websites

| Area | What sites normally learn | JBrowser |
|---|---|---|
| Page Visibility API | When you switch tabs or minimise | Page always looks visible |
| Focus / blur | When you click into another window | No window blur/focus, `hasFocus()` is true |
| Fullscreen | When you press F11 / leave fullscreen | User-initiated fullscreen isn't reported |
| Extensions | Which extensions you have installed | Probing `chrome-extension://` gives the same answer whether or not an extension is installed |
| User-Agent + Client Hints | Exact version, OS version, CPU arch, device model | Generic Google Chrome UA, reduced hints |
| History API | How many pages you visited in this tab | `history.length` clamped |
| DevTools detection | That you opened DevTools (console getters, `debugger` timing, window size, F12 keydown) | All of these are neutralised |
| Keyboard | Browser/OS shortcuts you press (F12, Ctrl+Tab, Ctrl+T, PrintScreen, Super), keystroke-timing biometrics, keyboard layout | Shortcuts never reach the page, key timing is jittered, layout map is standard |
| Automation | `navigator.webdriver` | Always `false` |

Each protection is a Chromium feature flag that's on by default. Turn any of them off in `chrome://flags` (search "JBrowser") if a site really needs it.

## Downloads

Releases: https://github.com/Jitheswar/JBrowser/releases

| Platform | Package |
|---|---|
| Windows 10/11 x64 | `JBrowser-<ver>-windows-x64-installer.exe` / portable `.zip` |
| Debian / Ubuntu / Mint / Pop!_OS | `jbrowser_<ver>_amd64.deb` (`sudo apt install ./jbrowser_*.deb`) |
| Red Hat / Fedora / Rocky / Alma / openSUSE | `jbrowser-<ver>.x86_64.rpm` (`sudo dnf install ./jbrowser-*.rpm`) |
| Arch / Manjaro / EndeavourOS | [`packaging/arch/PKGBUILD`](packaging/arch/PKGBUILD) (`makepkg -si`) |
| Any Linux | `jbrowser-<ver>-linux-x64.tar.xz` (extract and run `./jbrowser`) |

## Building

See [docs/BUILDING.md](docs/BUILDING.md). Short version on Linux:

```bash
./scripts/fetch.sh          # official Chromium source at the pinned tag (depot_tools)
./scripts/apply-patches.sh  # apply patches/series
./scripts/build.sh          # gn gen + ninja
./scripts/package-linux.sh  # .deb, .rpm, .tar.xz
```

## Testing

`tests/detection/` is a page that runs every spying technique listed above. `tests/run_detection.py <browser>` runs it automatically: it switches tabs, attaches DevTools and sends keys while the page watches.

## License

BSD-3-Clause for JBrowser's own patches and scripts. Chromium and its components keep their own licenses.
