# JithuBrowser

**A privacy-focused browser built on official Chromium.** Websites keep working, including Chrome-only ones, and Chrome Web Store extensions install normally. Pages just can't watch what you do.

> Status: **work in progress, no release yet.** All protections are implemented and pass the 14-test privacy suite on a Linux dev build of Chromium 155 (stock Chrome 155 fails 12 of the 14). Release packages are not built yet. The download table below describes the planned release packages; nothing is published until a GitHub release exists.

## What JithuBrowser hides from websites

| Area | What sites normally learn | JithuBrowser | Status |
|---|---|---|---|
| Page Visibility API | When you switch tabs or minimise (`document.hidden`, `visibilitychange`, `freeze`/`resume`, visibility timeline, service-worker `clients.matchAll()`) | Page always looks visible | verified (dev build, tests pass) |
| Focus / blur | When you click into another window (`blur`, `focus`, `hasFocus()`) | Page always believes its window is focused | verified (dev build, tests pass) |
| Window geometry & fullscreen | OS window size/position, F11 fullscreen (`outerWidth`, `screenX`, `display-mode`) | Derived from the page viewport; browser fullscreen looks like a normal window | verified (dev build, tests pass) |
| History | How many pages you visited in the tab (`history.length`) | Clamped to 2 | verified (dev build, tests pass) |
| Automation | `navigator.webdriver` | Always `false` | verified (dev build, tests pass) |
| User-Agent + Client Hints | Exact version, OS version, device model | Looks like stock Google Chrome; high-entropy hints reduced | verified (dev build, tests pass) |
| Keyboard layout | Your physical layout/language via `navigator.keyboard.getLayoutMap()` | Standard US QWERTY | verified (dev build, tests pass) |
| Typing rhythm | Keystroke timing biometrics | Key event timestamps are jittered (monotonic, never in the future); `performance.now()` inside a handler is not jittered | verified (dev build, tests pass) |
| Browser shortcuts | Which shortcuts you press (Ctrl+F, Ctrl+T, F5, ...) | Handled by the browser, never offered to the page (cut/copy/paste still reach the page so web editors work) | verified (dev build, tests pass) |

Not hidden, because the page legitimately needs it: the characters you type into a page's own text fields and the keys you press while a page has focus and no browser shortcut matches.

Each protection is a Chromium feature that is on by default. Turn one off if a site breaks, for example:

```bash
jithubrowser --disable-features=JithuBrowserHideVisibility,JithuBrowserProtectKeyboard
```

Feature names: `JithuBrowserHideVisibility`, `JithuBrowserHideFocus`, `JithuBrowserHideWindowGeometry`, `JithuBrowserHideHistoryLength`, `JithuBrowserHideAutomation`, `JithuBrowserReduceClientHints`, `JithuBrowserProtectKeyboard`, `JithuBrowserKeystrokeJitter`.

See [docs/ROADMAP.md](docs/ROADMAP.md) for what is still planned and [docs/DESIGN.md](docs/DESIGN.md) for limits (what a page can still work out).

## Downloads (planned)

Prebuilt packages, so nobody has to compile Chromium, will appear at https://github.com/Jitheswar/JithuBrowser/releases

| Platform | Package |
|---|---|
| Windows 10/11 x64 | `JithuBrowser-<ver>-windows-x64-installer.exe` / portable `.zip` |
| Debian / Ubuntu / Mint / Pop!_OS | `jithubrowser_<ver>_amd64.deb` (`sudo apt install ./jithubrowser_*.deb`) |
| Red Hat / Fedora / Rocky / Alma / openSUSE | `jithubrowser-<ver>.x86_64.rpm` (`sudo dnf install ./jithubrowser-*.rpm`) |
| Arch / Manjaro / EndeavourOS | [`packaging/arch/PKGBUILD`](packaging/arch/PKGBUILD) (`makepkg -si`) |
| Any Linux | `jithubrowser-<ver>-linux-x64.tar.xz` (extract and run `./jithubrowser`) |

## Building

See [docs/BUILDING.md](docs/BUILDING.md). Short version on Linux:

```bash
./scripts/fetch.sh          # official Chromium source at the pinned tag (depot_tools)
./scripts/apply-patches.sh  # apply patches/series
./scripts/build.sh          # gn gen + ninja
./scripts/package-linux.sh  # .deb, .rpm, .tar.xz
```

Windows: `scripts\windows\build.ps1` then `scripts\windows\package.ps1` (portable zip + Inno Setup installer).

## Testing

`tests/test_privacy.py` (pytest + Playwright) checks each protection against a browser binary: `JITHU_BROWSER=/path/to/binary pytest tests/`. Run it against stock Chrome first; the UA, Client Hints, history, `webdriver` and keyboard tests should fail there and pass on JithuBrowser. `tests/detection/` is a manual page that runs the same probes. Tab-switch and minimise tests need a real window manager; a display-less cluster cannot hide windows.

## License

BSD-3-Clause for JithuBrowser's own patches and scripts. Chromium and its components keep their own licenses.
