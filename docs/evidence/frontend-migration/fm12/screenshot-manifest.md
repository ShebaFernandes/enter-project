# FM12 screenshot and accessibility manifest

## Capture matrix

| Capture | Viewport / zoom | Purpose |
| --- | --- | --- |
| `organization-1440-1x` | 1440×1000 / 100% | Wide organization workspace |
| `organization-1024-1x` | 1024×768 / 100% | Compact desktop behavior |
| `organization-390-1x` | 390×844 / 100% | Mobile form and publication-action reflow |
| `organization-320-1x` | 320×844 / 100% | Minimum-width reflow |
| `organization-1440-2x` | 1440×1000 / 200% | Reflow under document zoom |

The Chromium suffix is appended by Playwright. Goldens are stored under
`app/tests/browser/fm12-organization.spec.ts-snapshots/`. Fixture tests mock HTTP
only inside Playwright; the separate authenticated scenario exercises a real
Django session, DRF, PostgreSQL, CSRF, tenant scoping and immutable synthetic
provenance.

## Intentional adaptations

- The mockup's admin organization tools are split into four semantic cards so
  each independent write has its own status and recovery area.
- Internal opening state and public publication remain visually and
  operationally separate. Publication adds a reviewed-field preview and
  explicit confirmation because the static mockup does not model this
  production boundary.
- Synthetic fixtures use a persistent warning and explicit confirmation instead
  of resembling real candidate entry. Contact and resume controls are absent.
- Saved search creation accepts the authoritative owned search ID rather than
  allowing an independently supplied opening context.
- Loading, empty, authorization failure and stale-ETag states are production
  controls not represented by the static mockup.

## Automated accessibility coverage

Every capture asserts no page-level horizontal overflow and no serious/critical
axe findings. Forms, navigation, publication actions, confirmation dialogs and
live status messages are named and keyboard reachable. These checks complement,
but do not replace, the manual accessibility gate deferred until after FM14.
