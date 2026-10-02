# FM11 screenshot and accessibility manifest

## Capture matrix

| Capture family | Viewport / zoom | Purpose |
| --- | --- | --- |
| `progress-1440-1x`, `rights-1440-1x` | 1440×1000 / 100% | Wide application timeline and rights history |
| `progress-1024-1x`, `rights-1024-1x` | 1024×768 / 100% | Compact desktop behavior |
| `progress-390-1x`, `rights-390-1x` | 390×844 / 100% | Mobile navigation, actions and history |
| `progress-320-1x`, `rights-320-1x` | 320×844 / 100% | Minimum-width reflow |
| `progress-1440-2x`, `rights-1440-2x` | 1440×1000 / 200% | Reflow under document zoom |

The Chromium suffix is appended by Playwright. Goldens are stored under
`app/tests/browser/fm11-candidate-control.spec.ts-snapshots/`. Fixture tests mock
HTTP only inside Playwright; the separate authenticated scenario exercises real
Django sessions, DRF, PostgreSQL, CSRF, application and privacy service paths.

## Intentional adaptations

- The static mockup's progress widget becomes a per-application timeline sourced
  only from published candidate-facing status history.
- The mockup has no privacy-rights screen, so the page follows the approved rights
  contract and existing legacy behavior while using the shared visual foundation.
- Destructive withdrawal and deletion are dialogs with explicit safe cancel paths.
- Loading, empty, stale-write, expiry, held, failure and escalation states are
  production controls not represented by the static mockup.

## Automated accessibility coverage

Every capture asserts no page-level horizontal overflow and no serious/critical
axe findings. Forms, links, confirmation dialogs, status messages and request
history are named and keyboard reachable. These checks complement, but do not
replace, the manual accessibility gate deferred until after FM14.
