# FM13 screenshot and accessibility manifest

## Capture matrix

| Capture | Viewport / zoom | Purpose |
| --- | --- | --- |
| `governance-1440-1x` | 1440×1000 / 100% | Wide Tenant Admin overview |
| `governance-1024-1x` | 1024×768 / 100% | Compact desktop behavior |
| `governance-390-1x` | 390×844 / 100% | Mobile tabs and card reflow |
| `governance-320-1x` | 320×844 / 100% | Minimum-width navigation and content |
| `governance-1440-2x` | 1440×1000 / 200% | Reflow under document zoom |

The Chromium suffix is appended by Playwright. Goldens are stored under
`app/tests/browser/fm13-governance.spec.ts-snapshots/`. Fixture tests mock HTTP
only inside Playwright; the separate authenticated scenario exercises a real
Tenant Admin session, DRF, PostgreSQL, CSRF, audited reads and review creation.

## Intentional adaptations

- The mockup has no Tenant Admin governance screen, so the route uses the shared
  admin visual language and approved semantic tokens rather than inventing a
  mockup-equivalent candidate screen.
- Governance is divided into Overview, Audit metadata, Access reviews and
  Emergency access tabs to keep redacted evidence separate from consequential
  decisions.
- Review completion requires decisions for all pending items and one explicit
  confirmation. Bounded exceptions reveal owner/expiry fields only when chosen.
- Emergency grants expose minimized scope/expiry metadata and require explicit
  confirmation for revocation; candidate content remains absent.
- Loading, empty, failed-read and stale-ETag states are production controls not
  represented by the static mockup.

## Automated accessibility coverage

Every capture asserts no page-level horizontal overflow and no serious/critical
axe findings. Tabs support click plus ArrowLeft, ArrowRight, Home and End. Forms,
evidence, live status, destructive confirmations and cancellation paths are named
and keyboard reachable. These checks complement, but do not replace, the manual
accessibility gate deferred until after FM14.
