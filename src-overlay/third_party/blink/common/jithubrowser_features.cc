// Copyright 2026 The JithuBrowser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "third_party/blink/public/common/jithubrowser_features.h"

namespace jithubrowser::features {

BASE_FEATURE(kJithuBrowserHideVisibility, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserHideFocus, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserHideWindowGeometry, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserHideHistoryLength, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserHideAutomation, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserReduceClientHints, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserHideDevTools, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserProtectKeyboard, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserKeystrokeJitter, base::FEATURE_ENABLED_BY_DEFAULT);
const base::FeatureParam<int> kJithuBrowserKeystrokeJitterMaxMs{
    &kJithuBrowserKeystrokeJitter, "max_ms", 30};
BASE_FEATURE(kJithuBrowserHideExtensions, base::FEATURE_ENABLED_BY_DEFAULT);
BASE_FEATURE(kJithuBrowserBackgroundRealism, base::FEATURE_ENABLED_BY_DEFAULT);

}  // namespace jithubrowser::features
