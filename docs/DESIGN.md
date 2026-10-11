# Design notes and limits

* Patches are native (Blink/Chromium C++), not injected JavaScript, so they behave the same in iframes and workers and cannot be seen via `Function.prototype.toString`.
* Every protection is a base::Feature, enabled by default, individually switchable.
* Uniform beats random: the UA, hints, keyboard map and window geometry are the same for everyone, so JithuBrowser users blend together instead of becoming unique.

Limits
* A page that has focus sees the characters typed into its own fields and non-shortcut keys. Only browser-level keys, layout and timing are protected.
* Keystroke jitter changes event timestamps. A page that measures with `performance.now()` inside its own handler still sees real arrival times.
* Hidden tabs are still throttled internally for battery/CPU; script can observe throttling indirectly through timer drift (see roadmap item 4).
* Pages that do real-time work after a tab switch (video calls, exam software) may not behave the way their authors expect. Disable the relevant feature for such sites.
