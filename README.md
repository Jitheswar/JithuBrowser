# JithuBrowser

**A privacy-focused browser built on official Chromium.** Websites keep working, including Chrome-only ones, and Chrome Web Store extensions install normally. Pages just can't watch what you do.

> Status: **pre-release available** ([download](https://github.com/Jitheswar/JithuBrowser/releases)) for Linux x86_64 and Windows x64. All protections pass the 35-test privacy suite on Linux and, on the Windows build under Wine, 34 of 35 (the WebGL `readPixels` test is skipped there because Wine has no WebGL); stock Chrome fails 31 of the 35 on Linux and 28 on Windows. Real installs were verified on Ubuntu 22.04 (`.deb`), Fedora 44, Rocky Linux 9.8 and openSUSE Tumbleweed (`.rpm`), and Arch Linux (`makepkg` + `pacman`). The **Windows installer is cross-compiled and has not been run on real Windows.**

## What JithuBrowser hides from websites

| Area | What sites normally learn | JithuBrowser | Status |
|---|---|---|---|
| Page Visibility API | When you switch tabs or minimise (`document.hidden`, `visibilitychange`, `freeze`/`resume`, visibility timeline, service-worker `clients.matchAll()`) | Page always looks visible | verified (dev build, tests pass) |
| Focus / blur | When you click into another window (`blur`, `focus`, `hasFocus()`) | Page always believes its window is focused | verified (dev build, tests pass) |
| Window geometry & fullscreen | OS window size/position, F11 fullscreen (`outerWidth`, `screenX`, `display-mode`), and that you left a fullscreen page by switching tabs (`fullscreenchange`) | Derived from the page viewport; browser fullscreen looks like a normal window; a fullscreen page is not told when you switch tabs (fullscreen is restored when you return) | verified (dev build, tests pass) |
| Background-tab clocks | That your tab is hidden, from timer and animation-frame rates and from muted videos pausing (hidden tabs normally run at 1 Hz, stop `requestAnimationFrame` and pause video) | Hidden tabs keep running like visible ones (costs some CPU/battery) | verified (tests pass) |
| Find in page | What you searched for, via canary text in collapsed content (`beforematch`/`toggle` events) | Find skips collapsed content, so matches never signal the page (it will not find text inside closed accordions) | verified (tests pass) |
| Canvas / WebGL / audio fingerprints | Pixel-exact canvas output, your GPU/driver name (`UNMASKED_RENDERER`), exact offline-audio samples | Canvas readbacks (`getImageData`, `toDataURL`, `toBlob`) differ by at most 1 on about a quarter of the pixels, WebGL reports a generic GPU name, audio renders get a sub-audible change. Not covered: font probing and the many other ways to fingerprint | verified (tests pass) |
| Per-site switch | A site that breaks under a protection | App menu → **JithuBrowser protections for this site**, or the settings page `chrome://jithubrowser-settings` (list, add, remove), or `--jithubrowser-unprotected-sites=a.com,b.com`, turns the in-page protections off for that site and its subdomains. User-Agent, browser shortcuts and silent fullscreen stay on. The settings page can also hide JithuBrowser's two main-menu entries | verified (test passes) |
| Quiet mode (opt-in) | Chromium's own background requests to Google (component updates, push messaging, account and time checks) | `--jithubrowser-quiet-google` stops them. Trade-offs: Widevine and certificate-revocation lists stop updating, no web push. New-tab-page and search warmup requests and the spellcheck dictionary download are not covered | verified (test passes) |
| History | How many pages you visited in the tab (`history.length`, `navigation.entries()`) | Clamped to 2 | verified (dev build, tests pass) |
| Automation | `navigator.webdriver` | Always `false` | verified (dev build, tests pass) |
| User-Agent + Client Hints | Exact version, OS version, device model | Looks like stock Google Chrome; high-entropy hints reduced | verified (dev build, tests pass) |
| Keyboard layout | Your physical layout/language via `navigator.keyboard.getLayoutMap()` | Standard US QWERTY | verified (dev build, tests pass) |
| Typing rhythm | Keystroke timing biometrics (via `event.timeStamp` or `performance.now()` in a key handler) | Key events arrive after a random delay of up to 20 ms (order preserved; about 10 ms extra latency per character) and timestamps are jittered | verified (tests pass) |
| Browser shortcuts | Which shortcuts you press (Ctrl+F, Ctrl+T, F5, ...) | Handled by the browser, never offered to the page (cut/copy/paste still reach the page so web editors work) | verified (dev build, tests pass) |

Not hidden, because the page legitimately needs it: the characters you type into a page's own text fields and the keys you press while a page has focus and no browser shortcut matches.

Each protection is a Chromium feature that is on by default. Turn one off if a site breaks, for example:

```bash
jithubrowser --disable-features=JithuBrowserHideVisibility,JithuBrowserProtectKeyboard
```

Feature names: `JithuBrowserHideVisibility`, `JithuBrowserHideFocus`, `JithuBrowserHideWindowGeometry`, `JithuBrowserHideHistoryLength`, `JithuBrowserHideAutomation`, `JithuBrowserReduceClientHints`, `JithuBrowserProtectKeyboard`, `JithuBrowserKeystrokeJitter`, `JithuBrowserKeepHiddenTabsActive`, `JithuBrowserPrivateFindInPage`, `JithuBrowserSilentTabFullscreenExit`, `JithuBrowserFarbleCanvas`, `JithuBrowserFarbleWebGL`, `JithuBrowserFarbleAudio`, `JithuBrowserSiteSettings`, `JithuBrowserUpdateCheck`. Quiet mode is a command-line switch, not a feature.

See [docs/ROADMAP.md](docs/ROADMAP.md) for what is still planned and [docs/DESIGN.md](docs/DESIGN.md) for limits (what a page can still work out).

## Install (beginner's guide)

You do **not** need to compile anything. Download the ready-made file for your computer, install it, done.

> **Status:** JithuBrowser is an early project. Pre-releases for **Linux** and **Windows** are on the [Releases page](https://github.com/Jitheswar/JithuBrowser/releases). The Windows installer has not been tested on real Windows yet.

### Step 1: Which computer do you have?

| You use | Go to |
|---|---|
| Windows 10 or 11 | [Windows](#windows) |
| Ubuntu, Linux Mint, Debian, Pop!_OS | [Debian / Ubuntu family](#debian-ubuntu-linux-mint-pop_os) |
| Fedora, RHEL 9+, Rocky 9+, Alma 9+, openSUSE | [Fedora / RPM family](#fedora-rhel-9-rocky-9-alma-9-opensuse) |
| Arch, Manjaro, EndeavourOS | [Arch family](#arch-manjaro-endeavouros) |
| Another Linux | [Any Linux](#any-linux-no-install-needed) |
| macOS / iPhone / Android | Not supported yet |

Not sure which Linux you have? Open a terminal and type `cat /etc/os-release`. The first lines name your distribution.
Your computer must be 64-bit (x86_64). ARM computers such as a Raspberry Pi are not supported yet.

Every file comes from **https://github.com/Jitheswar/JithuBrowser/releases**. Scroll to **Assets** and click the file you need.

### Windows

1. Download the file ending in `-windows-x64-installer.exe`.
2. Double-click it. A setup window with a progress animation opens and shows when JithuBrowser is installed (add `--silent` to hide the window).
3. **If Windows shows a blue "Windows protected your PC" screen:** the installer is not signed with a paid code-signing certificate, which is normal for new open-source projects. Click **More info**, then **Run anyway**. Only do this for a file you downloaded from the Releases page above.
4. Follow the installer, then open **JithuBrowser** from the Start menu.

> **The Windows build is cross-compiled on Linux. It passes the privacy tests under Wine but has not been run on real Windows.** Expect rough edges, and please [report problems](https://github.com/Jitheswar/JithuBrowser/issues). Do not install it next to Chromium on the same PC.

### Debian, Ubuntu, Linux Mint, Pop!_OS

1. Download the file ending in `_amd64.deb`.
2. Open a terminal in the folder where it was saved (usually **Downloads**) and run (use your file's name):

   ```bash
   sudo apt install ./jithubrowser_*_amd64.deb
   ```
3. Start it from your application menu, or run `jithubrowser`.

Needs Debian 11+ or Ubuntu 20.04+ (or newer).

### Fedora, RHEL 9+, Rocky 9+, Alma 9+, openSUSE

1. Download the file ending in `.x86_64.rpm`.
2. In a terminal, in the folder where it was saved:

   ```bash
   sudo dnf install ./jithubrowser-*.x86_64.rpm      # Fedora, RHEL, Rocky, Alma
   sudo zypper install ./jithubrowser-*.x86_64.rpm   # openSUSE
   ```
3. Start it from your application menu, or run `jithubrowser`.

RHEL, Rocky and Alma **8** (and older) are too old to run it.

### Arch, Manjaro, EndeavourOS

1. Install the build tools once: `sudo pacman -S --needed base-devel git`
2. Get the recipe and install:

   ```bash
   git clone https://github.com/Jitheswar/JithuBrowser.git
   cd JithuBrowser/packaging/arch
   makepkg -si
   ```

   This does **not** compile Chromium. It downloads the finished release and packages it for pacman.

### Any Linux (no install needed)

1. Download the file ending in `-linux-x64.tar.xz`.
2. Extract it and run it:

   ```bash
   tar -xf jithubrowser-*-linux-x64.tar.xz
   cd jithubrowser-*-linux-x64
   ./jithubrowser
   ```
3. If it says the sandbox cannot start, run this once in that folder and try again:

   ```bash
   sudo chown root:root chrome-sandbox && sudo chmod 4755 chrome-sandbox
   ```

### Check your download (optional, recommended)

Each release has a `SHA256SUMS` file that lets you confirm your download is complete and unmodified.

- Linux: put it next to your download and run `sha256sum -c SHA256SUMS --ignore-missing`. You should see `OK`.
- Windows (PowerShell): run `Get-FileHash .\yourfile.exe` and compare the value with the one in `SHA256SUMS`.

### First start: what to expect

- JithuBrowser looks and works like Chrome. Websites that only work in Chrome should work here.
- To hide what you do, it makes pages see a normal Chrome. A few things differ on purpose: video you expect to pause in a background tab may keep playing, and some web apps will not notice that you switched tabs.
- Chrome Web Store extensions are meant to work, but this has not been tested on every release yet.
- Streaming sites that use DRM (Netflix and similar) have not been tested.
- If a site breaks, turn a protection off (names are listed above). On Linux, start from a terminal like this:

  ```bash
  jithubrowser --disable-features=JithuBrowserProtectKeyboard
  ```

### Updating and uninstalling

JithuBrowser checks GitHub once, 30 seconds after it starts, and shows a bar when a newer release exists; it never installs anything by itself. To update on **Windows**, click **Install update**: the browser downloads the installer from the release, checks its SHA-256 against the release's `SHA256SUMS`, and starts it (the setup window shows progress; restart JithuBrowser when it says it is done). On **Linux** the bar opens the download page: install the new package the same way as before (updating needs administrator rights there). Your bookmarks and settings are kept. This check is one plain HTTPS request to `api.github.com` with no cookies; turn it off with `--disable-features=JithuBrowserUpdateCheck`.

| System | Uninstall |
|---|---|
| Windows | Settings → Apps → JithuBrowser → Uninstall |
| Debian / Ubuntu family | `sudo apt remove jithubrowser` |
| Fedora / RPM family | `sudo dnf remove jithubrowser` |
| Arch family | `sudo pacman -R jithubrowser-bin` |
| Tarball | delete the folder |

Your personal data (profile) is stored separately from Chromium's. On Linux that is `~/.config/jithubrowser` and `~/.cache/jithubrowser`; delete them too for a completely clean removal.

### Something went wrong?

- **"command not found: jithubrowser"**: log out and back in, or start it from the application menu.
- **A "missing library" (`.so`) error**: your Linux is older than 2020. Use a newer version of your distribution.
- **Blank window or crash on start**: try `jithubrowser --disable-gpu` and tell us about it.
- Anything else: [open an issue](https://github.com/Jitheswar/JithuBrowser/issues) and include your operating system and what you saw.

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

- `tests/run-tests.sh /path/to/browser`: the 35-test privacy suite (pytest) on a virtual display with a window manager, so tab switches and minimising are real. Run it against stock Chrome as a control: the leak tests fail there and pass on JithuBrowser.
- `tests/run-tests-wine.sh /path/to/wine /path/to/out/JithuBrowser-win`: the same suite for the Windows build under Wine.
- `tests/site_sweep.py`: loads 20 real websites and flags "unsupported browser" notices; run it on stock Chrome as a control.
- `tests/extension_check.py <dirs>`: loads Manifest V3 extensions and checks that they really run.
- `tests/sandbox_check.sh <browser>`: run as a normal user (`scripts/enter-rootfs-user.sh bash tests/sandbox_check.sh <browser>`) to confirm the browser's own sandbox engages without `--no-sandbox`.
- `tests/detection/` is a manual page that runs similar probes.

## License

BSD-3-Clause for JithuBrowser's own patches and scripts. Chromium and its components keep their own licenses.
