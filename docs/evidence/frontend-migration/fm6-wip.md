# FM6 initial checkpoint — historical, superseded

The owner subsequently approved reconciliation and the direct Search → Results
journey. The blocker below is historical, not the current product decision.
Current implementation/verification is tracked in [fm6.md](./fm6.md). Uncertain,
unsafe or unvalidated interpretation still blocks execution inline; this is not
an authorization to ignore `requires_review`. Prior fallback coverage is retained.

Scope: FM6-01 → FM6-02 → FM6-03, dependent on completed FM5-03. No FM7 work.
All FM6 task markers and the umbrella acceptance gate remain unchecked.

## Implemented, not accepted

- Independent `recruiter-results-page` flag for the existing search route's
  `?view=results` state; escaped Django bootstrap, exclusive React template and
  same-URL legacy rollback.
- React SearchResults, ResultsToolbar, ResultCard, CandidateDetail, Evidence,
  EmploymentTimeline and Finding using FM2 components/tokens.
- Existing encrypted results restore/display/page and comparison-selection
  create/read/PATCH APIs; server ordering retained, no search replay or browser
  storage, optimistic ETag handling and safe comparison destination.
- Fresh candidate-detail authorization on each opening/retry. A denied detail
  read removes its stale card and blocks comparison pending authorized refresh.
- Standalone candidate route remains legacy under the plan's shared-route gate
  until FM7. Management/disclosure controls were not migrated or removed.
- Full employment history is unavailable in the existing detail schema; its
  component says Unavailable instead of inventing a chronology or widening APIs.

Files added: `app/frontend/react/candidate-detail.tsx`, `search-results.tsx`,
`search-results.css`, `app/frontend/templates/recruiter/react_results.html`,
`app/tests/contract/test_fm6_routes.py`, `app/tests/browser/fm6-results.spec.ts`,
`fixtures/fm6.html`, `recruiter/fm6-authenticated.spec.ts`, and new FM6 screenshots.
Edited by this implementation: React entry registry, server frontend registry,
search page bootstrap and browser bootstrap helper (FM6 verification origin).
No models, migrations, APIs, authorization services or legacy feature code changed
by this implementation.

## Focused verification so far

- Test-first route test failed as expected before implementation.
- Implemented route/rollback/shared-candidate-gate tests: 2 passed.
- Focused browser components: 4 passed (responsive/detail, denied reads,
  ordered selection/concurrency, empty/throttled/degraded states).
- New screenshot baselines cover results/detail at 1440×1000, 1024×768,
  390×844, 320×844 and 200% document zoom. Both results/detail axe checks pass
  with zero serious/critical violations. These are provisional, not final signoff.
- Mypy: 232 source files, no issues. Ruff and frontend check passed at the
  preceding focused checkpoint. React build passed. A final small focus-return
  change has not been rebuilt/verified yet.
- Complete PostgreSQL/browser suites have NOT been run for FM6.
- Authenticated FM6 flow is blocked before review: the home bypass described
  below navigates directly to results. Do not remove the review assertion.

## Blocking concurrent changes

The working tree was clean at the start of this task. During implementation,
changes appeared in three files this implementation did not edit:

1. `app/frontend/react/search-home.tsx`: removes the `requires_review` branch
   and always executes interpreted criteria, including when the server requires
   recruiter review.
2. `app/tests/browser/fm4-home.spec.ts`: adds a test asserting direct execution
   despite `requires_review: true` and zero criteria-review handoff requests.
3. `app/config/settings/local.py`: enables `recruiter-results-page` and
   `criteria-review-page` locally.

These overlap the active acceptance journey and conflict with the requested
preservation of server-authoritative workflow and default-off FM6 rollout.
They were preserved, not reverted. No FM6 task can be signed off while the
authoritative review response is bypassed. Direction is required to reconcile
these edits; an intentional workflow change would require separate approved
scope/contracts, not silent FM6 migration behavior.

Temporary verification servers started for this task are stopped. FM6 is not
complete and FM7 is not cleared. Original mockup has not been edited.
