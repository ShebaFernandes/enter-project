# FM10 screenshot and accessibility manifest

## Capture matrix

| Capture family | Viewport / zoom | Purpose |
| --- | --- | --- |
| `jobs-1440-1x`, `role-1440-1x` | 1440×1000 / 100% | Wide directory and two-column role/application |
| `jobs-1024-1x`, `role-1024-1x` | 1024×768 / 100% | Compact desktop behavior |
| `jobs-390-1x`, `role-390-1x` | 390×844 / 100% | Mobile single-column reflow |
| `jobs-320-1x`, `role-320-1x` | 320×844 / 100% | Minimum-width reflow |
| `jobs-1440-2x`, `role-1440-2x` | 1440×1000 / 200% | Reflow under document zoom |

The Chromium suffix is appended by Playwright. Goldens are stored under
`app/tests/browser/fm10-public-application.spec.ts-snapshots/`. The fixture mocks
HTTP only inside Playwright; the separate authenticated scenario exercises the
real Django, DRF, PostgreSQL, session, CSRF, consent and application service path.

## Intentional mockup adaptations

- The jobs directory is a real data-backed destination rather than a dead link.
- The public role includes only the allowlisted public projection and never
  exposes tenant or internal opening identifiers.
- Application eligibility explains the clean-resume and role-consent requirement.
- Loading, empty, disappeared-role, duplicate, authentication and safe retry
  states are production controls not represented by the static mockup.
- The approved lowercase `enter` wordmark and local/system fonts remain in use;
  no remote font or invented brand asset was introduced.

## Automated accessibility coverage

Every capture asserts no page-level horizontal overflow and no serious/critical
axe findings. Forms, checkboxes, links and status messages are named and keyboard
reachable. These checks complement, but do not replace, the manual accessibility
gate deferred until after FM14.
