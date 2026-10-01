# FM7 screenshot and accessibility manifest

## Capture matrix

| Set | Location | Coverage |
| --- | --- | --- |
| Deterministic FM7 component goldens | `app/tests/browser/fm7-management.spec.ts-snapshots/management-{width}-{zoom}-chromium.png` | 1440×1000, 1024×768, 390×844, 320×844, 1440×1000 at 200% document zoom |
| Authenticated synthetic management | `docs/evidence/frontend-migration/fm7/management-live-{width}-{zoom}x.png` | Same matrix, real Django session/API, notes, shortlist, finding and status |
| Complete legacy/reference recapture | `docs/evidence/frontend-migration/fm7/regression-baselines/` | Existing FM1 production and immutable mockup states, chooser/live-public states |
| Machine-readable legacy/reference manifest | `regression-baselines/manifest.json` | Screenshot state names and accessibility findings |

Component goldens use synthetic HTTP fixtures only in tests. Production uses only
authorized APIs. Live captures are evidence, not deterministic screenshot goldens:
synthetic note creation times and generated resources can vary between runs.

## Reference and intentional differences

The immutable FM1 `mockup-detail-*`, `mockup-notes-*` and action/share/feedback
states are the reference for restrained paper/surface/ink colors, cards, controls
and section vocabulary. The original mockup is unchanged. FM7 reuses FM2's existing
semantic spacing, typography, border, radius and focus tokens without arbitrary
page styles.

- The approved production candidate route is a standalone authorized workspace,
  not the mockup's modal layered over mock results. Profile/Notes/Actions/Contact
  navigation uses in-page section links so the extra production controls remain
  visible and keyboard reachable. This is an intentional layout/interaction
  difference, not pixel-identical modal parity.
- Work/application selection, independent shortlist/internal status, structured
  feedback, conflicts, explicit publication and consent/field/destination preview
  add required production controls and text absent from the mockup.
- No mock contact links, salary, inferred employment data or contact history are
  invented. Undisclosed fields say Unavailable; absent values remain Unknown.
- Temporary lowercase `enter` text wordmark, local/system sans, Georgia-compatible
  display and system monospace remain the approved asset fallback. No remote fonts
  or replacement logo artwork are used.
- History-list and delivery polling gaps are described in `../fm7.md`, not filled
  with mock records or optimistic delivery claims.

## Accessibility-oriented review

- One main landmark, working skip link, named recruiter navigation and distinct
  candidate-section navigation; logical heading levels and explicitly labeled
  controls are asserted/reviewed.
- FM2 visible-focus styling retained. Skip-link Enter moves focus to main.
- Dialog initial focus, Shift+Tab trapping, Escape cancellation and confirmation
  are exercised; canceling a disclosure sends nothing. No automatic status change.
- Conflict region receives focus; no stale automatic resubmission.
- Loading/status use live regions; errors use alerts; unavailable/denied content
  is removed instead of showing a saved copy.
- Component and authenticated page axe checks require zero serious/critical
  violations at all five captures; horizontal overflow is asserted absent.
- Tests exercise 320px and 200% document zoom. This is not a claim of a physical
  screen-reader/device laboratory session; keyboard and accessible-name coverage
  is browser-driven.

Final full-suite result: **90 passed**, including every authenticated gate. See
`../fm7.md` for PostgreSQL and quality results. Component and live FM7 scans found
zero serious/critical accessibility violations.
