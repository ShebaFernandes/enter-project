# FM7 — recruiter management and disclosure

Scope: FM7-01 → FM7-02 → FM7-03, dependent on FM6-03. No FM8 work.
All three FM7 tasks are complete after the final regression gates below.
The FM1–FM14 umbrella acceptance checklist remains unchecked.

## Initial process and acceptance result

The interrupted test process was no longer running; local PostgreSQL was healthy.
The preserved `test_fm7_routes.py` was rerun alone: **1 failed**, at the missing
React-renderer assertion (expected test-first failure). The subsequent route
implementation exposed an error-template reverse with missing tenant context on
403; the fallback now safely links to platform selection when context is absent.
The focused route/CandidateWork/disclosure set subsequently passed **9 tests**.

## Route and components

Only `/tenants/{tenant_id}/recruiter/candidates/{candidate_id}/` is registered for
FM7. The flag is `recruiter-candidate-management-page`; the older unapproved
`recruiter-candidate-page` flag remains ineffective, preserving FM6 coverage.
Both base and local committed settings contain empty route-flag dictionaries.
Verification enables flags only in isolated server processes.

`CandidateManagement` coordinates fresh reads and in-memory drafts;
`NotesPanel`, `InternalStatus`, `ShortlistControl`, `PublicationPreview`,
`DisclosurePreview` and `DeliveryFeedback` are semantic presentation boundaries
built from the existing FM2 controls, cards, dialogs, conflict panel and tokens.
No new stylesheet, reset, remote font or private browser store is introduced.

Django supplies escaped tenant/candidate UUID bootstrap data. The shared mount
checks the current session; the same-origin client attaches trusted tenant and
CSRF context, credentials and no-store fetch behavior. Legacy scripts never mount
inside the React root. Missing assets fail to legacy; disabling the flag restores
the same URL and existing legacy template without changing data.

## Data, authorization and concurrency

- Existing authorized candidate detail/search context is fetched before showing
  profile, work and notes, and again before every mutation. Each existing mutation
  endpoint remains authoritative. Denial clears protected content and drafts.
- Visibility-return reloads current authorization. Pagehide/unmount aborts requests
  and clears the React tree; generation checks discard obsolete responses.
- Existing CandidateWork and actual linked Application are separate selectable
  contexts. Notes and internal status target only the selected aggregate. No fake
  application is created and no records are merged. Drafts must be saved/discarded
  before switching contexts. Server-owned status history remains unchanged.
- Notes are private by default; explicit hiring-team visibility uses the existing
  server-authorized field. Unsaved drafts remain in memory only.
- Internal Not relevant feedback requires explicit confirmation; cancellation
  restores the prior draft state without a write. Candidate-facing publication is
  separate, available only for an actual application, and requires its own preview
  and confirmation with the preview's current ETag. No notification is requested
  implicitly. The eight-value candidate-facing model remains unchanged.
- HTTP 409 never triggers an automatic overwrite. Current/attempted values are
  displayed by the existing conflict panel. Reload/discard and explicit reviewed
  resubmission remain separate user actions. Publication conflicts cannot replace
  a CandidateWork ETag.
- Disclosure shows the server-returned destination and permitted/excluded fields.
  Confirmation freshly revalidates authorization and the backend rechecks consent,
  visibility, purpose and field scope. Input changes invalidate a preview. Pending
  feedback is never described as delivered; uncertain mutations do not auto-retry.
  Identical in-memory retries reuse their idempotency key.
- SHORT_TENURE uses the existing neutral Finding component; no score, eligibility,
  status, ordering, recommendation or outcome logic was added.

No APIs, contracts, models, migrations, RLS policies, audit behavior, AI behavior,
search execution or handoff implementation changed.

## Existing API limitations retained explicitly

There is no authorized history-list GET or disclosure-result polling GET in this
phase's contract. History continues to be recorded server-side; the UI states that
the list is unavailable rather than fabricating entries. Delivery feedback uses
the returned state only. The application read context does not return previous
structured feedback: the form explicitly explains that newly submitted feedback
replaces current internal feedback while historical events remain intact. No
broader candidate endpoint is used to fill these gaps.

## Verification

- Expanded FM7 component/browser acceptance: **9 passed** before final regression.
- Authenticated synthetic search → React results → management passed, including
  note persistence, shortlist persistence, two-tab conflict, refresh, Back, sign-out,
  informational finding and empty localStorage/sessionStorage.
- Final clean PostgreSQL suite: **353 passed, 1 skipped** (354 collected). The
  existing PostgreSQL audit trigger prevents constructing the skipped tamper fixture.
- The first full run exposed review-only fixtures whose valid prompts now complete
  directly under the approved search behavior. Fixture prompts are now explicitly
  ambiguous and assert awaiting-review state; no security assertions were removed
  and no production interpretation/handoff behavior changed. The entire suite was
  rerun after this correction, not merely the failing tests.
- Repository-wide `mypy .`: **233 source files, no issues**.
- Ruff format/lint, Django system checks, migration drift: **passed**.
- TypeScript, ESLint, Prettier; legacy, React, WIP and showcase Vite builds: **passed**.
- Complete browser/accessibility regression: **90 passed**, all authenticated
  environment gates enabled with fresh one-time bootstrap URLs (2.4 minutes).
  This includes Tenant Admin, candidate application, recruiter legacy/FM4/FM5/FM6,
  FM7 management, comparison, publication, rollback and style-isolation coverage.
- No prior tests were deleted. The local development `app/db.sqlite3` artifact is
  intentionally untracked and covered by the repository ignore rules; PostgreSQL
  remains the authoritative development and verification database.

See [screenshot manifest](fm7/screenshot-manifest.md) for captures, intentional
visual differences and accessibility-oriented checks.

## Immutable reference

Both repository and original external HTML SHA-256 remain:
`daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

FM8 is cleared as the next task, but remains unstarted. Production route activation
is a separate rollout decision; no React production flag was enabled.
