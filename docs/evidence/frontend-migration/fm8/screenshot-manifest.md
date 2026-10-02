# FM8 screenshot and accessibility manifest

## Capture matrix

| Capture | Viewport / zoom | Purpose |
| --- | --- | --- |
| `comparison-1440-1-chromium.png` | 1440×1000 / 100% | Wide side-by-side comparison |
| `comparison-1024-1-chromium.png` | 1024×768 / 100% | Compact desktop comparison |
| `comparison-390-1-chromium.png` | 390×844 / 100% | Mobile stacked cards |
| `comparison-320-1-chromium.png` | 320×844 / 100% | Minimum-width reflow |
| `comparison-1440-2-chromium.png` | 1440×1000 / 200% | Reflow under document zoom |

All deterministic goldens are stored under
`app/tests/browser/fm8-comparison.spec.ts-snapshots/`. Their test fixture mocks
HTTP only inside Playwright; production renders data returned by authorized APIs.

## Reference and intentional differences

The immutable mockup comparison overlay is the visual reference for restrained
paper/surface/ink colors, evidence grouping, candidate columns and removal
controls. The source mockup was not modified.

- The production page is a standalone authorized route rather than an overlay on
  mock search results. This keeps the workflow URL, safe fallback and return path
  explicit.
- Narrow layouts use stacked semantic candidate cards rather than compressing a
  wide table or requiring page-level horizontal scrolling.
- Known, Unknown and Unavailable labels are explicit production requirements not
  fully represented in the mockup.
- Selection count, authorization-change messages, safe retry/return behavior and
  ETag-aware removal are required production controls absent from the mockup.
- No score, ranking, recommendation, generated summary or employment-decision
  control is shown.
- The approved temporary lowercase `enter` wordmark and local/system font stacks
  remain in use; no remote font or invented logo asset was introduced.

## Accessibility-oriented review

The Playwright checks assert a main landmark, named heading and controls, live
loading/status announcements, alert failures, visible keyboard focus, removal
focus recovery, no protected browser storage, no serious/critical axe findings
and no horizontal page overflow at every capture size. The 320px and 200% zoom
captures verify content-driven reflow. These automated checks do not replace the
manual assistive-technology gate deferred until after FM14.
