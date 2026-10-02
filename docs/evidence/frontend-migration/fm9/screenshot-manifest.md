# FM9 screenshot and accessibility manifest

## Capture matrix

| Capture | Viewport / zoom | Purpose |
| --- | --- | --- |
| `profile-1440-1-chromium.png` | 1440×1000 / 100% | Wide profile and visibility layout |
| `profile-1024-1-chromium.png` | 1024×768 / 100% | Compact desktop profile |
| `profile-390-1-chromium.png` | 390×844 / 100% | Mobile single-column form |
| `profile-320-1-chromium.png` | 320×844 / 100% | Minimum-width reflow |
| `profile-1440-2-chromium.png` | 1440×1000 / 200% | Reflow under document zoom |

All deterministic goldens are stored under
`app/tests/browser/fm9-profile.spec.ts-snapshots/`. Their fixture mocks HTTP only
inside Playwright; the authenticated acceptance test exercises the real Django,
DRF and PostgreSQL path.

## Reference and intentional differences

The immutable mockup candidate portal is the visual reference for restrained
paper/surface/ink colors, profile sections, employment editing, preferences and
resume completion. The source mockup was not modified.

- The production route loads only candidate-authorized server data and makes
  profile, visibility and publication operations visibly separate.
- Visibility choices describe the actual audience and consent consequences
  instead of implying that publication makes the profile public to everyone.
- Resume state is explicit about quarantine, scanning and parsing. There is no
  pre-scan download link, and manual entry remains available after failure. The
  production React page now includes a responsive drag-and-drop target alongside
  its accessible file input.
- Extracted employment facts include source and confidence labels and require
  candidate review rather than being silently accepted.
- Parsed suggestions start unchecked and affect only the editable draft after an
  explicit apply action; unsupported/unscoped facts stay manual-review-only.
- Conflict reconciliation, safe retry, loading, validation and failure states are
  production controls not fully represented in the static mockup.
- The approved temporary lowercase `enter` wordmark and local/system font stacks
  remain in use; no remote font or invented logo asset was introduced.

## Accessibility-oriented review

Playwright asserts a main landmark, named headings and controls, live status and
alert announcements, explicit resume states, no protected browser storage, no
serious/critical axe findings and no horizontal page overflow at every capture
size. The 320px and 200% zoom captures verify content-driven reflow. These
automated checks do not replace the manual assistive-technology gate deferred
until after FM14.
