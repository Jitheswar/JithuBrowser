# Roadmap

Done: page visibility, focus, window geometry/fullscreen (including silent exit from fullscreen on tab switch), `history.length` and the Navigation API, `navigator.webdriver`, User-Agent and Client Hints, keyboard layout, typing rhythm, browser shortcuts, private Find in page, hidden-tab realism, canvas/WebGL/audio fingerprint farbling, per-site switch, update notification, Linux packages (tar.xz/deb/rpm/Arch), Windows installer with an animated setup window.

Next (not started)
1. Stop stock Chromium's own requests to Google services (component updater, `android.clients.google.com`, `www.google.com` and similar) or make them opt-in. They are unchanged today.
2. WebGL `readPixels`, `AnalyserNode` and font-probing protection; screen-size buckets.
3. A settings page for the per-site list (today: app-menu toggle, prefs file, command-line switch).
4. Install updates automatically (needs a signed update channel and, on Linux, a package repository).
5. Run the Windows installer on real Windows; test with real root (setuid sandbox helper) and with paid DRM streaming.
6. Code-signing for the Windows installer; macOS and ARM builds (not planned for now).

Out of scope: spoofing that a required extension is installed, and hiding DevTools / console / debugger-timing detection. Sites that need an extension should get the real one.
