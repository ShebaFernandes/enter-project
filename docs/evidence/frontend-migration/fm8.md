# FM8 — candidate comparison

Scope: FM8-01 → FM8-02 → FM8-03, dependent on FM7-03. No FM9 work.
All three FM8 tasks are complete after the verification recorded below. The
FM1–FM14 umbrella acceptance checklist remains unchecked.

## Test-first acceptance

FM8 began with a route contract and four browser acceptance scenarios. Before
implementation, the route contract failed because the comparison route had no
React renderer, and all four component scenarios failed because the page was not
registered. These were the expected red tests for FM8 rather than regressions in
the legacy comparison.

The first passing implementation run exposed two accessibility defects in the
new UI: duplicated status wording and 3.15:1 label contrast. Both were corrected
before acceptance. A later combined regression exposed a focus-return race after
removing a candidate; focus recovery now waits for the updated enabled control.
The focused React and legacy comparison set then passed **7 tests**.

## Route and renderer boundary

The exact route is `/tenants/{tenant_id}/recruiter/comparison/`. Django continues
to own authentication, tenant membership and renderer selection. The independent
flag is `recruiter-comparison-page`; committed base and local settings still use
empty route-flag dictionaries, so production remains on the legacy renderer.

With the flag enabled, Django emits only escaped bootstrap context (`page`,
`tenantId`, `requiresSession`), a CSRF token, the React root and a safe recovery
fallback. `CandidateComparison` is the page boundary, with `SelectionSummary`,
`ComparisonGrid` and `EvidenceValue` as semantic subcomponents. React and legacy
code never own the same subtree. Disabling the flag restores the legacy template
at the same URL without a schema change or data replay.

## Authorized comparison flow

1. React reads the opaque workflow-handoff token from the URL fragment. It does
   not place the token, candidate identifiers or comparison data in browser
   storage.
2. It fetches the server-owned comparison selection with the trusted tenant and
   workflow-handoff headers. The shared API client supplies same-origin session,
   CSRF and no-store behavior.
3. It posts the current authorized candidate IDs to the existing deterministic
   comparison endpoint with an idempotency key.
4. The backend reauthorizes every candidate on every request and returns a stable
   evidence projection. Values are explicitly labelled Known, Unknown or
   Unavailable; missing evidence is never guessed.
5. If authorization changed, React reconciles the handoff selection using its
   current ETag and explains the removal. A denial clears protected data instead
   of leaving a cached comparison visible.
6. Removing a candidate updates the existing handoff with `If-Match`, reloads
   server-authoritative comparison data and returns keyboard focus to a surviving
   removal control or the return action.
7. Return navigation uses only the server-authorized handoff destination.

Comparison is read-only business behavior. It does not write CandidateWork,
Application, shortlist, internal status or candidate-facing status records. It
does not generate a score, winner, recommendation or employment decision.
`SHORT_TENURE` remains a neutral informational finding and cannot change ordering.
No API, model, migration, RLS policy, audit rule or background worker was added.

## States and accessibility

- Missing handoff context shows actionable empty guidance without fake data.
- Loading is announced and controls cannot submit duplicate operations.
- Expired, denied or unavailable context fails closed and removes protected data.
- Candidate cards use consistent field order and readable non-color state labels.
- The grid is side-by-side on wide screens and stacks at narrow widths without
  page-level horizontal overflow.
- Automated axe scans found no serious or critical violations across 1440×1000,
  1024×768, 390×844, 320×844 and 1440×1000 at 200% document zoom.
- Keyboard removal and focus return are asserted. This is browser automation
  evidence, not a claim of a physical screen-reader laboratory review.

See the [screenshot manifest](fm8/screenshot-manifest.md) for the capture matrix
and intentional differences from the immutable mockup.

## Verification

- Focused FM8 route/API/security/handoff set: **21 passed**.
- Complete PostgreSQL pytest suite: **354 passed, 1 skipped**. The existing audit
  trigger prevents constructing the intentionally skipped tamper fixture.
- Deterministic FM8 browser/accessibility/visual suite: **4 passed**.
- Authenticated real Django/PostgreSQL search → results → comparison → remove →
  return journey: **1 passed**, using an isolated flag-on server and a one-time
  synthetic session. Temporary verification settings were removed afterwards.
- Combined React and legacy comparison regression after focus repair: **7 passed**.
- Complete Chromium browser regression: **79 passed, 16 skipped**. The skipped
  cases require optional authenticated bootstrap environment variables; FM8's
  authenticated case was executed separately as described above.
- TypeScript, ESLint and Prettier: **passed**. Legacy, React, WIP and showcase
  production builds: **passed**.
- Ruff lint and format: **passed**. Mypy: **164 source files, no issues**.
- Django system checks and migration-drift check: **passed; no changes detected**.
- `git diff --check`: **passed**. No configured post-execution extension hooks
  were present.

## Immutable reference and next gate

Both repository and original external HTML SHA-256 remain:
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

FM9 is cleared as the next phase but remains unstarted. Production activation of
the FM8 React route is a separate rollout decision; its committed flag is off.
