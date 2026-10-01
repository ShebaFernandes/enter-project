# FM4 screenshot manifest — 2026-10-01

Immutable reference SHA-256 (both repository and original external file):
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

## Reference and implementation

| Set | Location | Sizes/states |
|---|---|---|
| Immutable mockup | `../fm1-baselines/mockup-search-home-*`, `mockup-sidebar-*` | Original four widths and 200% zoom |
| Deterministic FM4 assertions | `app/tests/browser/fm4-home.spec.ts-snapshots/` from repository root | Home/sidebar at 1440×1000, 1024×768, 390×844, 320×844; 640px at 200% exercises 320 CSS-pixel reflow |
| Authenticated current implementation | `search-home-live-{width}-{zoom}x.png`, `sidebar-live-{width}-{zoom}x.png` beside this manifest | Four required viewports and 1440×1000 at 200%; real synthetic-authorized backend records |
| Existing-page regression capture | `regression-baselines/manifest.json` | Complete FM1 authenticated surfaces, immutable mockup states and current FM3 jobs captures; old FM1 evidence was not overwritten |

No production UI uses fixture data. Component fixtures intercept APIs only inside
Playwright. Authenticated screenshots use the existing synthetic bootstrap commands.

## Intentional differences

- Approved lowercase text wordmark and system fonts replace missing approved logo
  and remote fonts. No invented logo and no network font dependency.
- Existing FM2 header and explicit Sign out replace mockup-only identity controls.
  Search/Results/Candidate demo navigation is not offered as a fake workflow.
- Composer remains centered at the mockup's 680px content width. Explicit authorized
  opening selector, speech button/status and readable Search label increase its
  height relative to the icon-only single-line mockup. Mobile controls wrap.
- Project/recent toggle and close have visible text labels; the narrow-screen panel
  is modal for focus containment and Escape/focus return. Native selects are retained.
- Recents use generic numbered labels and saved names rather than exposing raw
  prompt history in the sidebar. Both resolve authorized backend records.
- Real empty/unavailable/throttled states replace demo records. Suggested prompts
  only fill the editable composer; they never submit or authorize a search.

Review caught and corrected transparent sidebar token references, modal focus
return, and a long real-opening select overflowing at 320px. These are corrections,
not accepted visual exceptions. Reference files were not modified.
