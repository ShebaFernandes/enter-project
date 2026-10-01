# FM6 screenshot manifest

Immutable reference: repository `enter_recruiter_recruiter_candidate_ux.html` and
FM1/FM4 mockup results/profile captures. SHA-256:
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

| Set | Location | States / sizes |
| --- | --- | --- |
| Deterministic React component goldens | `app/tests/browser/fm6-results.spec.ts-snapshots/` | `results-{1440,1024,390,320}-1-chromium.png`, `results-1440-2-chromium.png`; corresponding `detail-*` files |
| Authenticated production API results | `docs/evidence/frontend-migration/fm6/` | `results-live-{1440,1024,390,320}-1x.png`, `results-live-1440-2x.png` |
| Full regression legacy/mockup captures | `docs/evidence/frontend-migration/fm6/regression-baselines/` | Existing FM1 screen inventory, chooser and immutable mockup, four widths and zoom |

1440 uses height1000; 1024 uses768; 390/320 use844. 2x means 200% document zoom.
Visual comparisons retain accessible production controls, authorization/minimized
content, unknown states and explicit applied criteria. See [FM6 evidence](../fm6.md)
for intentional differences, test coverage and final status. Mockup was never edited.
