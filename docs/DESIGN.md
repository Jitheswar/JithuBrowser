# Design notes and limits

* Patches are native (Blink/Chromium C++), not injected JavaScript, so they behave the same in iframes and workers and cannot be seen via `Function.prototype.toString`.
* Every protection is a base::Feature, enabled by default, individually switchable.
* Uniform beats random: the UA, hints, keyboard map and window geometry are the same for everyone, so JithuBrowser users blend together instead of becoming unique.

## Known limits (from an independent multi-agent audit of the patches)

These are not hidden today; the first few are the ones a determined hostile page can still use.

* **A page can still see that a modifier key (Control/Alt/Shift) went down**, but not which shortcut it belonged to: measured with real key presses, the page sees only `Control`, not the `f`/`t`/`l` that follows, and holding a shortcut produces no auto-repeat events. Hiding the modifier itself would break Ctrl+click and games.
* **Other APIs that only work while visible/focused** (auto Picture-in-Picture, Compute Pressure, WebAuthn, pointer lock, gamepad, sensors, lazy-loaded iframes) may still behave differently when the tab is hidden or unfocused; muted-video pausing, timers and animation frames were measured and no longer differ.
* **`history.length` is clamped to 2**, which can confuse sites that count entries (some "return to start" and pushState-counting code).
* Browser-initiated fullscreen exit on tab switch is still delivered to a page that was in fullscreen.
* Installed web-app windows (`TYPE_APP`) do not get shortcut reservation (upstream gives apps all keys).

**Find in page no longer reports your search to the page** (`JithuBrowserPrivateFindInPage`): pages can plant hidden "canary" text in `hidden=until-found` blocks or closed `<details>` and learn what you searched for from the `beforematch`/`toggle` events a match triggers (stock Chrome does this). Find now skips collapsed content, so it will not find text inside closed accordions until you open them.

**Typing rhythm and history depth are now closed too** (`JithuBrowserKeystrokeJitter`, `JithuBrowserHideHistoryLength`): key-down and key-up events reach the page after a random delay of up to 20 ms (order is preserved, and a click can never overtake a keystroke), so timing measured with `performance.now()` inside a key handler is blurred as well as `event.timeStamp`; the cost is about 10 ms of extra latency on average for each typed character. The Navigation API now shows at most the current entry and the one before it, like `history.length`; entries beyond that cannot be reached with `navigation.traverseTo()`.

**Background-tab throttling is now closed** (feature `JithuBrowserKeepHiddenTabsActive`): hidden, minimised and occluded tabs keep painting and are not throttled, like a tab that is being screen-captured, so timers and `requestAnimationFrame` run at the same rate as in a visible tab. The price is some extra CPU/battery for background tabs; in one synthetic test a hidden tab running a heavy animation used about 9 percentage points more of a CPU core. Turn it off with `--disable-features=JithuBrowserKeepHiddenTabsActive` if you have many busy background tabs.

Fixed during the audit: `Document::hidden()` now stays truthful for Blink's own scheduling/animation code and only the JavaScript-visible `document.hidden`/`visibilityState` are spoofed; browser-fullscreen media queries are computed on the main thread; shortcut reservation no longer breaks Escape, fullscreen pages or Linux text-editing hotkeys; Wake Lock, `navigator.vibrate()`, `screen.avail*`, `screen.isExtended` and mouse `screenX/Y` no longer leak the same state.
