# FM9 — candidate profile and resume flow

Scope: FM9-01 → FM9-02 → FM9-03, dependent on FM8-03. No FM10 work.
All three FM9 tasks are complete after the verification recorded below. The
FM1–FM14 umbrella acceptance checklist remains unchecked.

## Test-first acceptance

FM9 began with a route contract and four browser acceptance scenarios. Before
implementation, the route contract failed because `/candidate/profile/` had no
React renderer, and the component scenarios failed because the page was not
registered. These were the expected red tests for FM9.

The first authenticated Django/PostgreSQL journey exposed a real integration
defect: the OpenAPI and React client use `application/merge-patch+json`, but the
DRF profile view accepted only ordinary JSON and returned HTTP 415. A narrowly
scoped merge-patch parser and contract regression test now protect that public
media type. No profile business rule was moved into the frontend.

## Route and renderer boundary

The exact route is `/candidate/profile/`. Django continues to own session
authentication and renderer selection. The independent route flag is
`candidate-profile-page`; committed base settings and local environment defaults
retain an empty route-flag dictionary, so the default renderer remains legacy.
Local Compose may opt in with an explicit process-only environment value; that
development preview mechanism is not read by production settings.

With the flag enabled, Django emits only escaped bootstrap context (`page` and
`requiresSession`), a CSRF token, the React root and a safe recovery fallback.
`ProfilePage` owns the React subtree and composes `ProfileSection`,
`EmploymentEditor`, `Preferences`, `VisibilityConsent`, `ResumeUploader` and
`ScanState`. Disabling the flag restores the legacy template at the same URL
without a migration or data replay.

## Candidate-controlled flow

1. React loads the current candidate-owned profile through the existing
   `/api/v1/candidate/profile` endpoint. Protected profile data is never written
   to localStorage or sessionStorage.
2. Candidate edits remain local until the explicit save action. Profile PATCH
   sends the current ETag, a fresh idempotency key, CSRF and the approved merge
   patch media type.
3. Visibility is saved separately through the existing visibility endpoint.
   The UI explains each audience and requires explicit consent information; it
   never presents publication as universal recruiter access.
4. A stale ETag shows the shared reconciliation panel. The candidate may reload
   the authoritative version, review local changes or explicitly retry using the
   fresh server ETag; there is no automatic overwrite.
5. Publication calls the existing publish operation and preserves backend
   validation as the authority for completeness, active consent and clean resume
   requirements.
6. Resume upload uses the existing grant, direct object upload and status-polling
   operations. Pending/quarantined content has no download link. Scan and parse
   failures retain manual profile entry and do not silently approve extracted
   facts.
7. Candidates may choose a file or drag it onto the responsive drop zone. After
   clean scanning and parsing, source-backed suggestions are shown unchecked.
   Selecting and applying supported suggestions changes only the editable draft;
   it does not save or publish. Facts that cannot map safely to one field remain
   visible as manual-review evidence and cannot be misleadingly selected.

No new model, migration, RLS rule, audit operation, outbox event or worker was
introduced. The React page uses only the FM9-approved existing APIs.

The browser does not read or parse resume contents. Actual suggestions appear
only after the existing external malware-scan and private parser integration
records source-backed facts through the resume service. This change completes
the candidate drop/review/apply experience and its API consumption; it does not
pretend that LocalStack is a malware scanner or add an unapproved browser-side
parser. Until that external integration is configured, a real local upload may
remain in its pending quarantine state and manual entry remains available.

## States and accessibility

- Loading, save, publish, validation, conflict and failure states are announced.
- Employment facts show their source and date-confidence state and remain
  candidate reviewable.
- Resume pending, quarantine, scan failure, parse failure and manual-entry
  recovery are explicit; pre-scan download is absent.
- Controls are labelled, keyboard reachable and disabled during duplicate work.
- The desktop grid collapses to one column without page-level horizontal
  overflow at narrow widths.
- Automated axe scans found no serious or critical violations across 1440×1000,
  1024×768, 390×844, 320×844 and 1440×1000 at 200% document zoom.
- This is automated browser evidence, not a claim of a completed physical
  screen-reader laboratory review.

See the [screenshot manifest](fm9/screenshot-manifest.md) for the capture matrix
and intentional differences from the immutable mockup.

## Verification

- Focused FM9 route and candidate-rights contracts: **14 passed**.
- Focused profile, visibility, resume, authorization, RLS and validation set:
  **50 passed**.
- Complete PostgreSQL pytest suite: **356 passed, 1 skipped**. The existing audit
  trigger prevents constructing the intentionally skipped tamper fixture.
- Deterministic FM9 browser/accessibility/visual suite: **5 passed**, including
  a real browser `drop` event, no pre-approval overwrite and selected draft
  autofill.
- Authenticated real Django/PostgreSQL profile edit → visibility consent →
  publish journey: **1 passed**, using an isolated flag-on server and one-time
  candidate session. Temporary verification settings were removed afterwards.
- Complete Chromium browser regression: **84 passed, 17 skipped**. Skips require
  optional authenticated bootstrap environment variables; FM9's authenticated
  case was executed separately as described above.
- TypeScript, ESLint and Prettier: **passed**. Legacy, React, WIP and showcase
  production builds: **passed**.
- Ruff lint and format: **passed**. Mypy: **164 source files, no issues**.
- Django system checks and migration-drift check: **passed; no changes detected**.
- Local Compose configuration with the default-off preview pass-through:
  **valid**.
- `git diff --check`: **passed**. No configured post-execution extension hooks
  were present.

## Immutable reference and next gate

Both repository and original external HTML SHA-256 remain:
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

FM10 is cleared as the next phase but remains unstarted. Production activation
of the FM9 React route is a separate rollout decision; its committed flag is off.
