// Copyright 2026 The JithuBrowser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef THIRD_PARTY_BLINK_PUBLIC_COMMON_JITHUBROWSER_FEATURES_H_
#define THIRD_PARTY_BLINK_PUBLIC_COMMON_JITHUBROWSER_FEATURES_H_

#include "base/feature_list.h"
#include "third_party/blink/public/common/common_export.h"

// JithuBrowser privacy protections. Every protection is enabled by default and can
// be turned off individually from chrome://flags or --disable-features=.
namespace jithubrowser::features {

// Page Visibility API always reports "visible"; no visibilitychange,
// visibility-state performance entries, freeze/resume events or wasDiscarded.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideVisibility);

// Pages always believe their window is focused: no window blur/focus events,
// document.hasFocus() stays true, :focus is not lost when switching windows.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideFocus);

// Window geometry does not reveal DevTools docking or user fullscreen (F11):
// outerWidth/outerHeight follow the viewport, screenX/Y are 0 and the
// display-mode media query never matches "fullscreen" for browser fullscreen.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideWindowGeometry);

// history.length never reveals how many pages were visited in this tab.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideHistoryLength);

// navigator.webdriver is always false.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideAutomation);

// The User-Agent string and Client Hints look like stock Google Chrome, with
// high-entropy hints reduced (no model, no exact versions).
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserReduceClientHints);

// DevTools cannot be detected: console arguments are never inspected with
// page-observable side effects, `debugger` statements never pause and
// DevTools does not fetch source maps from the site.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideDevTools);

// Browser/OS shortcuts (DevTools, tab switching, fullscreen, PrintScreen,
// Super/Meta) never reach pages, and the keyboard layout map is standard US.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserProtectKeyboard);

// Keyboard events are delivered with a small random delay (order preserved)
// so typing rhythm cannot be used as a biometric fingerprint.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserKeystrokeJitter);

// Maximum keystroke delay in milliseconds for kJithuBrowserKeystrokeJitter.
BLINK_COMMON_EXPORT extern const base::FeatureParam<int>
    kJithuBrowserKeystrokeJitterMaxMs;

// Web pages cannot probe chrome-extension:// URLs to learn which extensions
// are installed (web accessible resources only load via per-session URLs).
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserHideExtensions);

// Background tabs behave like foreground tabs as far as script can tell:
// timers and requestAnimationFrame are not throttled, media is not paused.
BLINK_COMMON_EXPORT BASE_DECLARE_FEATURE(kJithuBrowserBackgroundRealism);

}  // namespace jithubrowser::features

#endif  // THIRD_PARTY_BLINK_PUBLIC_COMMON_JITHUBROWSER_FEATURES_H_
