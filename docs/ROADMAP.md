# Roadmap

Done (code written, first build pending): visibility, focus, window geometry/fullscreen, `history.length`, `navigator.webdriver`, UA + Client Hints, keyboard layout map, keystroke timestamp jitter, browser-shortcut reservation, Linux packaging (tar.xz/deb/rpm/Arch), Windows build + installer scripts.

Next
1. First verified build and test run (stock Chrome vs JithuBrowser).
2. Releases: attach prebuilt Linux and Windows packages so users never compile.
3. Hide which extensions are installed from `chrome-extension://` probing (not started).
4. Background-tab realism: stop timer/rAF throttling from revealing a hidden tab (not started; see docs/DESIGN.md).
5. Fingerprinting: canvas/WebGL/audio/font surface, screen size buckets.
6. Per-site feature overrides in settings UI.
7. Auto-update channel.

Out of scope: spoofing that a required extension is installed. Sites that need an extension should get the real one; JithuBrowser only stops sites from *enumerating* what you have.
