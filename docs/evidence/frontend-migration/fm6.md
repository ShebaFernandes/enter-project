# FM6 — results, authorized detail and approved direct search

Scope: FM6-01 → FM6-02 → FM6-03, after verified FM5-03. FM7 is not implemented.
FM6-01, FM6-02 and FM6-03 pass. The FM1–FM14 umbrella gate remains unchecked.

## Product decision and reconciliation

Normal journey: Search input → Search → Results. Search is the recruiter's
explicit execution instruction only for a validated interpretation. `requires_review`,
ambiguities, unavailable/invalid AI output and malformed criteria stop on home
with inline clarification. No automatic retry of uncertain execution. A completed
search whose result handoff fails retries only transport, using the same retry key.

Specification, plan, frontend-migration, OpenAPI handoff metadata/interpretation
descriptions, authorization matrix, AI boundaries and FM6 tasks record this narrow
amendment. No models, migrations, ranking, eligibility or AI gateway implementation
changed. Legacy home uses the same safe interpretation gate. Historical fallback
tests now enter internal review explicitly rather than requiring it in the normal journey.

## Routes, components and authorization

- Existing `/tenants/{tenant}/recruiter/search/?view=results` uses the independent
  `recruiter-results-page` server flag. Both base and local settings have `{}`.
- ResultsToolbar, ResultCard, CandidateDetail, Evidence, EmploymentTimeline and
  Finding reuse FM2 shell, tokens, controls, alerts, loading, empty states and dialogs.
- Applied criteria come from the freshly authorized SEARCH_RESULTS metadata.
  Adjust criteria opens the existing CriteriaReview/GroupEditor within a dialog,
  using a separate encrypted CRITERIA_REVIEW token. Human edits, stable IDs,
  ANY/ALL, estimated impact, ETags and explicit revised execution are retained.
- A handoff equality fix compares stable-ID group/criterion collections independent
  of database retrieval order. Values and IDs must still match; execution, ranking,
  evidence and comparison request order are not changed.
- Results display/page restoration reuses the authorized persisted run, not search
  replay. Opaque fragment tokens support refresh/Back. Ordered comparison selection
  uses the existing session-bound service and ETags; conflict blocks stale overwrite.
- Candidate detail is fetched afresh using search context. Denial clears detail and
  removes its stale card, blocks comparison until refreshed, and provides safe feedback.
- The standalone candidate URL still owns management/disclosure and remains wholly
  legacy until FM7's shared-route gate. Its React flag is deliberately unregistered.
- No new API operation, authorization rule, RLS policy or browser store was introduced.
  No protected state writes occur in the migrated components. Live checks assert
  localStorage and sessionStorage are both empty after refresh and comparison return.

## Rollout and rollback

Production remains legacy. Local verification alone sets process flags. Switching
`recruiter-results-page` off restores the same URL to the complete legacy template,
with the same encrypted handoff and no data migration/mutation. Search home and
internal review flags remain independent. Missing manifests fail to legacy; each
page has one DOM owner. Legacy bundles never load React/Tailwind reset.

## Visual and accessibility evidence

See [screenshot manifest](./fm6/screenshot-manifest.md). Results and detail have
component goldens at 1440×1000, 1024×768, 390×844, 320×844 and 200% document zoom.
Live authenticated captures use the same sizes. Assertions cover no horizontal
overflow, dialog Escape/focus return, labeled controls, one main landmark,
async status/error announcements and zero serious/critical axe violations.
Keyboard and accessible-name checks use Playwright's accessibility-facing locators;
no claim is made of a physical assistive-technology/device lab session.

Intentional differences from immutable mockup:

- Approved text `enter`, system sans/monospace and Georgia display fallback; no
  remote fonts or invented logo. FM2 semantic paper/raised/ink/sage/hairline tokens.
- Larger accessible controls and explicit authorization, unknown, evidence and
  neutral finding copy increase card height. Desktop list retains a right action
  region; mobile collapses to one column. No fabricated avatars or private fields.
- Applied criteria and in-results adjustment are the owner's explicit amendment.
- Full employment chronology is not available in the approved detail schema;
  EmploymentTimeline says Unavailable, never infers dates. Confirmed finding evidence
  remains available. SHORT_TENURE has no scoring/ranking/status effect.
- No FM7 status, contact, notes or disclosure controls are copied into React; the
  existing authorized management link opens the complete legacy page.

## Verification record

- Fresh PostgreSQL full run: **350 passed, 1 existing skip**, **351 collected**.
  Skip: audit tamper fixture cannot be constructed past the PostgreSQL trigger.
- Repository-wide `mypy .`: **232 source files**, no issues; Ruff format/lint pass.
- Django system check: no issues. Migration drift: no changes detected.
- TypeScript, ESLint, Prettier and legacy/React/WIP/showcase Vite builds pass.
- Focused real-session FM6 journey and five component cases: **6 passed**.
- First full browser run: 76 passed / 2 failed (old automatic-review baseline
  entry and unnecessary fallback-label drift). Entry was reconciled without removing
  review coverage; fallback label restored. Final complete rerun: **79 passed,
  zero skipped**, including every environment-gated authenticated scenario.
- Existing PostgreSQL security coverage includes restricted-role RLS, tenant/session
  binding, current consent/visibility, negative authorization, CSRF and rate limits.
- Both immutable mockup copies SHA-256:
  `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

Authenticated verification uses existing one-time synthetic bootstrap on isolated
database `enter_fm4_verify_20261001`, cache DB11. Ports 8014/8015/8016 exercise
legacy, FM4 and internal FM5 respectively. Port8017 enables results for FM6.
Only its test process replaces the Bedrock gateway response with the existing
`deterministic_fallback(...).model_dump_json()` result, passed through the unchanged
LangGraph validator. Real Django sessions, PostgreSQL authorization, execution,
handoffs and candidate APIs remain in use. External Bedrock is not claimed tested;
production unavailable interpretation fails closed and no test gateway is configured
in committed settings. All environment-gated scenarios use fresh one-time URLs.

No existing test was deleted: tracked test cases remain, fallback entry assertions
were reconciled to the approved journey, and negative/no-execution coverage was added.
No mypy exclusions or screenshot tolerances were changed. Prior FM5 visual goldens
remain unchanged. FM6 screenshots were inspected at desktop and mobile; all intentional
content/layout differences are listed above rather than hidden by relaxed thresholds.

FM7 dependency is cleared, but FM7 has not begun. All route flags remain default-off;
no production cutover occurred. Branding assets and full employment-history data remain
documented limitations, not fabricated features. Temporary verification servers are
stopped after verification.
