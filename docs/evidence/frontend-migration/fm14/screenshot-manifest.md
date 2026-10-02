# FM14 screenshot manifest

The machine-readable source of truth is `authenticated-baselines/manifest.json`. It records the immutable mockup hash, confirms synthetic-only test data and lists every state's accessibility result.

## Capture summary

| Category | States | View configurations | Screenshots | Serious/critical axe violations |
|---|---:|---:|---:|---:|
| Production authenticated pages | 14 | 5 | 70 | 0 |
| Immutable mockup references | 12 | 5 | 60 | 0 |
| Total | 26 | 5 | 130 | 0 |

The five configurations are 1440×1000, 1024×768, 390×844, 320×844 and 1440×1000 at 200% CSS zoom. Filenames encode the state, viewport and zoom.

Production states cover search home, results, candidate detail dialog, comparison, candidate management direct navigation, disclosure, organization, criteria review, role application, profile/resume, progress, rights, governance and audit. Reference states cover chooser, candidate platform, search home, sidebar, results, detail, notes, action, comparison and the dormant public-profile, interpretation and admin panels.

`fm3-live/` additionally contains five public-jobs live captures at the same view configurations.

## Review notes

- The source mockup hash is `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.
- Production screenshots contain synthetic fixtures only.
- Production intentionally adds privacy, authorization and recovery controls absent from the static reference.
- Rights and governance are document-adapted screens because the reference has no direct equivalent.
- The approved text wordmark and system font stack are intentional implementation differences.
- A transient 97-pixel difference in one 320-pixel reference capture passed unchanged on isolated rerun; no visual baseline was rewritten.
- FM7 live evidence was refreshed with current synthetic records and timestamps; visual expectations were not relaxed.
- Automated checks supplement, but do not replace, the deferred Phase 10 physical assistive-technology review.
