# Roadmap

Done (code written, first build pending): visibility, focus, window geometry/fullscreen, `history.length`, `navigator.webdriver`, UA + Client Hints, keyboard layout map, keystroke timestamp jitter, browser-shortcut reservation, Linux packaging (tar.xz/deb/rpm/Arch), Windows build + installer scripts.

Next
1. First verified build and test run (stock Chrome vs JithuBrowser).
2. Releases: attach prebuilt Linux and Windows packages so users never compile.
3. Hide which extensions are installed from `chrome-extension://` probing (feature flag `JithuBrowserHideExtensions` is reserved).
4. Background-tab realism (`JithuBrowserBackgroundRealism` reserved): do not throttle timers/rAF for hidden tabs.
5. Fingerprinting: canvas/WebGL/audio/font surface, screen size buckets.
6. Per-site feature overrides in settings UI.
7. Auto-update channel.

Out of scope: spoofing that a required extension is installed. Sites that need an extension should get the real one; JithuBrowser only stops sites from *enumerating* what you have.
