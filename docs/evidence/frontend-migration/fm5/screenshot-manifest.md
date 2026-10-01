# FM5 screenshot manifest

Reference: immutable `enter_recruiter_recruiter_candidate_ux.html`, `#interp`.
Verified SHA-256:
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

| Capture | Location / pattern |
|---|---|
| Deterministic React review screenshot assertions | `app/tests/browser/fm5-review.spec.ts-snapshots/review-{width}-{zoom}-chromium.png` |
| Authenticated production React review | `docs/evidence/frontend-migration/fm5/review-live-{width}-{zoom}x.png` |
| Immutable mockup review | `docs/evidence/frontend-migration/fm1-baselines/mockup-dormant-interp-{width}x{height}-{zoom}x.png` |
| Fresh legacy/mockup regression captures | `docs/evidence/frontend-migration/fm5/regression-baselines/` |

Each review set includes 1440×1000, 1024×768, 390×844, 320×844 and 1440×1000
with 200% document zoom. Live captures contain synthetic authorized data only.
Tests use full-page screenshots, disabled screenshot animation and the existing
local/system font stacks; no remote font or original-mockup edit is used.

Intentional differences from the mockup:

- Approved lowercase text wordmark and local/system font fallbacks.
- No original raw prompt restored, and no invented candidate career timeline.
- Real grouped criteria editing with explicit stable membership, operators,
  purposes and typed values, rather than mockup free-text parsing/chips.
- Explicit privacy/refresh notices, ETag conflict recovery and failure controls.
- Only safe return-to-search navigation; no mock tab that navigates to fictional data.
- Real authorized estimates replace mock numbers; expanded editors make the page
  taller and collapse to a single column below the FM2 workspace breakpoint.

Desktop and mobile captures were inspected for panel width, paper/ink colors,
serif hierarchy, border/radius/shadow, labeled control spacing and clipping. The
added production controls account for the structural differences. Screenshot
assertions detect unexplained changes to the accepted FM5 rendering on future runs.
