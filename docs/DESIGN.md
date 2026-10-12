# Design notes and limits

* Patches are native (Blink/Chromium C++), not injected JavaScript, so they behave the same in iframes and workers and cannot be seen via `Function.prototype.toString`.
* Every protection is a base::Feature, enabled by default, individually switchable.
* Uniform beats random: the UA, hints, keyboard map and window geometry are the same for everyone, so JithuBrowser users blend together instead of becoming unique.

## Known limits (from an independent multi-agent audit of the patches)

These are not hidden today; the first few are the ones a determined hostile page can still use.

* **Keystroke jitter only changes `event.timeStamp`.** A page that calls `performance.now()` inside its own key handler still sees true timing.
* **Shortcut reservation is not airtight.** Auto-repeat key events and the Find bar can still reveal that a reserved shortcut was used.
* **Other APIs that only work while visible/focused** (media playback pausing, auto Picture-in-Picture, Compute Pressure, WebAuthn, pointer lock, gamepad, sensors, lazy-loaded iframes) still behave differently when the tab is hidden or unfocused.
* **Navigation API** (`navigation.entries()`) still shows true same-origin history depth; only `history.length` is clamped.
* **`history.length` is clamped to 2**, which can confuse sites that count entries (some "return to start" and pushState-counting code).
* Browser-initiated fullscreen exit on tab switch is still delivered to a page that was in fullscreen.
* Installed web-app windows (`TYPE_APP`) do not get shortcut reservation (upstream gives apps all keys).

**Background-tab throttling is now closed** (feature `JithuBrowserKeepHiddenTabsActive`): hidden, minimised and occluded tabs keep painting and are not throttled, like a tab that is being screen-captured, so timers and `requestAnimationFrame` run at the same rate as in a visible tab. The price is some extra CPU/battery for background tabs; in one synthetic test a hidden tab running a heavy animation used about 9 percentage points more of a CPU core. Turn it off with `--disable-features=JithuBrowserKeepHiddenTabsActive` if you have many busy background tabs.

Fixed during the audit: `Document::hidden()` now stays truthful for Blink's own scheduling/animation code and only the JavaScript-visible `document.hidden`/`visibilityState` are spoofed; browser-fullscreen media queries are computed on the main thread; shortcut reservation no longer breaks Escape, fullscreen pages or Linux text-editing hotkeys; Wake Lock, `navigator.vibrate()`, `screen.avail*`, `screen.isExtended` and mouse `screenX/Y` no longer leak the same state.
