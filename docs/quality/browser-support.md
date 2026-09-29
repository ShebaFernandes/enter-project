# Browser support and test matrix

Launch supports the current and immediately previous major versions of Chrome, Edge, Firefox, and Safari. Mobile coverage uses current Safari on iOS and current Chrome on Android. Unsupported browsers receive usable semantic content and typed-input fallbacks where practical.

Automated Chromium checks cover 320, 375, 768, 1024, and 1440 CSS pixels plus a 200% zoom/reflow case. Representative Firefox and WebKit flows run before release. Manual checks cover keyboard-only use, screen-reader smoke tests, text spacing, high contrast, reduced motion, speech fallback, file controls, and dialogs on representative desktop and mobile devices. Test evidence records exact browser and OS versions.
