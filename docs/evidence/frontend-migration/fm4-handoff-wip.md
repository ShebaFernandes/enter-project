# FM4 handoff remediation — historical WIP record

Superseded by [final FM4 verification](fm4.md): FM4 and remediation gates pass.
The earlier failures below are retained as history, not current blockers. Production
React flags remain default-off and no FM5 work has begun.

## Latest extension verification — 2026-10-01

The comparison scope question below is resolved by explicit user authorization.
`comparison-selection` now reuses SearchWorkflowHandoff with migration 0007
(`updated_at`, distinct kind); migration 0006 supplies forced tenant RLS.
Create/read/PATCH/DELETE use `/search-handoffs/comparison-selection`; POST `/return`
generates a separate results-bound token and approved same-origin route. No stored
or accepted arbitrary return URL. Ordered IDs are encrypted, max ten unique IDs,
ETag replacement returns 409 on stale writes. Current source membership, eligibility,
consent and field scope are checked on every operation; final comparison retains
its independent current authorization. Cleanup covers all handoff kinds.

Legacy criteria/results transport and comparison selection now use the same-origin
CSRF client and opaque fragments/headers, not browser storage. Search draft persistence
is removed; unsaved edits remain in DOM with a navigation warning. Retired recruiter
storage keys are deleted, not restored. Other candidate-page draft helpers remain
unchanged and outside this recruiter transport scope; they are not presentation-only
and must not be described as a repository-wide storage remediation. Native recruiter
forms use POST so failed JavaScript cannot serialize prompts/criteria into query URLs.

`SEARCH_WORKFLOW_HANDOFF_ENABLED=True` enables the verified legacy API transport;
it is independent of React route rollout. React route flags remain unchanged and
default-off. No React search component/route was added. FM4-R04–R06 are new unchecked
tasks. No tasks or umbrella checklist items have been marked complete.

Current checks:

- Focused PostgreSQL handoff/selection suite: **31 passed**, including restricted
  non-owner/non-BYPASSRLS comparison-table checks and no recruiting-record writes.
- Complete PostgreSQL pass: **336 passed, 1 skipped, 1 failed**. The failure was the
  FM3 manifest/rollback check overlapping a build; its focused rerun passed after
  builds completed. Two additional security tests were added and passed afterward.
  This is not a clean all-final-state full-suite completion claim.
- Complete browser pass: **41 passed, 9 skipped, 4 failed**. Three failures lacked
  WIP/showcase fixture bundles; one retained the now-forbidden draft-restoration
  expectation. All affected FM1/FM2 files were rerun: **10 passed**.
- Focused legacy comparison browser suite: **3 passed**, including focus/removal,
  320px/200% layout and serious/critical accessibility checks.
- New real authenticated legacy search → criteria (refresh) → results → comparison
  (refresh) → server-generated return → sign-out journey: **1 passed** against
  isolated database `enter_fm4_verify_20261001`. It asserts empty localStorage and
  sessionStorage and zero serious/critical axe findings. The first synthetic prompt
  matched no records; the final supported `Python` criterion passes. No auth bypass
  was added: existing one-time synthetic bootstrap was used.
- Repository-wide mypy: **229 files passed**. Ruff lint/format, Django checks and
  migration drift, TypeScript/ESLint/Prettier passed. Legacy/React/WIP/showcase builds
  passed. Original mockup hashes remain unchanged (recorded below).

Still outstanding: full 25-case browser/security acceptance mapping, all authenticated
scenarios, explicit Back/revocation/browser rollback evidence, results pagination
restoration (display currently returns only its persisted snapshot page), remaining
original handoff gates, FM4 React search/sidebar and visual evidence. **FM4 is not
complete and FM5 is not cleared.** Earlier notes below describe the pre-extension
checkpoint and are retained as history, not the current implementation state.

## Implemented WIP

Dedicated encrypted SearchWorkflowHandoff and migration 0006; hash-only random
token, actor/tenant/credential/session-key binding, 15-minute expiry, source version,
typed criteria/results references, ETag revision/revoke, bounded rotating retry,
metadata restore, separate current-authorized snapshot display and tenant cleanup.
Recent-search GET implementation is drafted. Planning clarification and unchecked
FM4-R01–R03 are added. OpenAPI alignment is **not yet complete**.

`SEARCH_WORKFLOW_HANDOFF_ENABLED` is default false; no production route is migrated.
The shared frontend transport helper is unreferenced WIP. Initial legacy integration
edits were reverted before activation because of the storage dependency below;
existing legacy source files are unchanged. No prior test was removed.

## Security integration finding

`frontend/recruiter/search.ts` calls `useSearchContext` on results initialization.
That calls `writeComparisonSelection` in `frontend/recruiter/comparison.ts`, which
persists tenant, search context, candidate IDs and `return_url: location.href` in
sessionStorage. With a fragment handoff URL, this also persists the bearer token.
`frontend/shared/persistence.ts` independently persists search prompts and criteria.
Replacing only REVIEW_KEY/RESULT_KEY is therefore insufficient.

Draft removal is within the approved scope. Comparison is a separate cross-page
workflow: its current page requires the persisted selection. Merely switching it
to memory loses the selection on full navigation and breaks the existing comparison
journey. Before claiming storage-free interoperability, resolve this dependency with
an explicitly typed authorized comparison selection transport (not arbitrary JSON),
or an approved changed selection/navigation behavior. No new comparison handoff type
or candidate-ID payload has been silently added to the two approved handoff schemas.

## Verification so far

19 focused PostgreSQL tests passed, including the default-disabled guard test:
valid restore, invalid states/session/type, encrypted/hash-only storage, retry bounds,
revoked credential/membership, rate limit, metadata-only results/completion, ETag,
CSRF, actor/tenant denial, audit/log inspection and non-owner/non-BYPASSRLS RLS.
Repository-wide `mypy .` passed (228 files), Ruff lint/format passed, Django checks
and migration drift passed, TypeScript/ESLint/Prettier passed, and both legacy and
React Vite builds passed. These are not the complete 24-case security gate.
Both mockup copies retain SHA-256
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.
The full PostgreSQL/browser/accessibility regression pass has not been run.

Still required: all authorization-loss/opening/team cases, result pagination parity,
concurrency review, strict OpenAPI response schemas, cleanup acceptance, storage-free
legacy/browser journeys, React FM4 home/sidebar, visual/accessibility evidence and
the complete regression/quality run. FM4-R01–R03 and FM4-01–03 remain unchecked.
FM5 is not cleared. The FM1–FM14 umbrella is unchanged.
