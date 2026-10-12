# JithuBrowser

**A privacy-focused browser built on official Chromium.** Websites keep working, including Chrome-only ones, and Chrome Web Store extensions install normally. Pages just can't watch what you do.

> Status: **pre-release available** ([download](https://github.com/Jitheswar/JithuBrowser/releases)) for Linux x86_64 and Windows x64. All protections pass the 19-test privacy suite on the Linux build (stock Chrome 155 fails 15 of the 19). The **Windows installer is cross-compiled and untested** on real Windows.

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
2. Double-click it.
3. **If Windows shows a blue "Windows protected your PC" screen:** the installer is not signed with a paid code-signing certificate, which is normal for new open-source projects. Click **More info**, then **Run anyway**. Only do this for a file you downloaded from the Releases page above.
4. Follow the installer, then open **JithuBrowser** from the Start menu.

> **The Windows build is cross-compiled on Linux and has never been run on Windows.** Expect rough edges, and please [report problems](https://github.com/Jitheswar/JithuBrowser/issues). Do not install it next to Chromium on the same PC.

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

JithuBrowser does not update itself yet. To update, download the newest release and install it the same way as before; your bookmarks and settings are kept.

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

`tests/test_privacy.py` (pytest) checks each protection against a browser binary: `tests/run-tests.sh /path/to/binary` (starts Xvfb + a window manager so tab switches and minimising are real). Run it against stock Chrome first as a control: the leak tests fail there and pass on JithuBrowser. `tests/detection/` is a manual page that runs similar probes.

## License

BSD-3-Clause for JithuBrowser's own patches and scripts. Chromium and its components keep their own licenses.
