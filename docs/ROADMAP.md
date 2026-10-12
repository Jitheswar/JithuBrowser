# Roadmap

Done: page visibility, focus, window geometry/fullscreen (including silent exit from fullscreen on tab switch), `history.length` and the Navigation API, `navigator.webdriver`, User-Agent and Client Hints, keyboard layout, typing rhythm, browser shortcuts, private Find in page, hidden-tab realism, canvas/WebGL/audio fingerprint farbling, per-site switch with a settings page, update notification and Windows auto-install, opt-in quiet mode for Chromium's Google requests, Linux packages (tar.xz/deb/rpm/Arch), Windows installer with an animated setup window.

Next (not started)
1. New-tab-page and search warmup requests, spellcheck dictionary download and Safe Browsing: make them opt-in too.
2. Font probing and screen-size buckets.
3. Install updates automatically on Linux (needs a signed update channel and a package repository), and run the Windows installer and auto-install on real Windows.
4. Test with real root (setuid sandbox helper) and with paid DRM streaming.
5. Code-signing for the Windows installer; macOS and ARM builds (not planned for now).

Out of scope: spoofing that a required extension is installed, and hiding DevTools / console / debugger-timing detection. Sites that need an extension should get the real one.
