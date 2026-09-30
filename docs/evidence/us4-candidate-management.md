# US4 candidate management and disclosure evidence

Verified 2026-09-30 with synthetic data only. Scope is Phase 7 tasks T121–T140.

## Candidate-work and application boundaries

- The first authorized candidate detail view creates or reuses one tenant-scoped `CandidateWorkRecord` for the candidate and originating search context. An opening is optional and, when supplied, must belong to the same tenant.
- Notes, shortlist changes, and internal-status changes reuse the same contextual record. Database constraints prevent duplicate contextual records.
- A later application can link to the matching candidate-work record, but remains a separate `Application`; linking does not merge or overwrite answers, consent, status, timestamps, or recruiter history.
- Candidate-controlled profile data and visibility remain authoritative. Candidate-work actions recheck current visibility and object, purpose, tenant, and field-scope authorization.

## Notes, shortlist, and internal status

- Recruiter notes have exactly one owner: an application or candidate-work record. Note content is encrypted, tenant/object authorized, conflict-protected with ETags, independently persisted, and excluded from audit payloads.
- Shortlisting is an explicit selection state only; it does not score, reject, publish a candidate-facing status, or trigger AI behavior.
- Internal status history is contextual. `Not relevant` requires a structured reason or note and supports cancellation that restores the prior state without affecting another application or candidate-work context.
- Status preview accepts only `InternalRecruitingStatus` and returns a nullable candidate-facing suggestion. `Offered` maps to `OFFER_MADE`; `Sourced`, `Not relevant`, `Hired`, and unknown states do not suggest publication.
- Candidate-facing publication remains restricted to the canonical eight values and requires an explicit valid selection, recruiter confirmation, current ETag, current consent/authorization, and idempotent notification enqueue. `SHORT_TENURE` remains informational only.

## Disclosure, consent, authorization, and audit

- Disclosure preview names the destination and purpose and computes the minimum authorized visible field set. Hiring-team destinations must match the contextual opening; email or WhatsApp destinations must match the candidate's stored destination.
- Confirmation rechecks candidate visibility, current consent, access grants, hiring-team/object access, field scope, preview integrity, and stale state at execution time. Cross-tenant and excessive-field attempts are denied.
- Confirmed delivery is represented by an outbox request and provider result feedback; no real WhatsApp delivery is performed. Idempotency prevents duplicate disclosure effects, and provider failure is retained as an auditable result.
- Candidate and tenant disclosure histories receive separate minimized audit records. View, note, shortlist, status, reason, conflict, disclosure, and notification-override events contain identifiers and field names rather than note, destination, or disclosed values.
- Forced PostgreSQL row-level security covers candidate-work, notes, shortlist, status events, and disclosure requests, including candidate ownership for disclosure history.

## UI and accessibility

- The recruiter management page supports keyboard-operable note, shortlist, internal-status, conflict-reconciliation, and disclosure-preview/confirmation flows.
- Server-saved state survives refresh. Sensitive note/reason text is not copied into browser storage; unsaved edits receive a navigation warning.
- The management flow reflows at 320 CSS pixels and passes the automated serious/critical accessibility scan.
- A one-time local synthetic recruiter session verified authenticated search, authorized evidence viewing, safe sign-out, and protected history.
- The original HTML mockup has no tracked or untracked changes.

## Commands and results

```text
DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgresql://enter:enter@127.0.0.1:5432/enter VALKEY_URL=redis://127.0.0.1:6379/0 uv run pytest -q
239 passed, 1 skipped (the PostgreSQL trigger intentionally prevents constructing the audit-tampering fixture)

uv run mypy config modules
Success: no issues found in 141 source files

uv run ruff format --check .
191 files already formatted

uv run ruff check .
All checks passed

python manage.py check
System check identified no issues

python manage.py makemigrations --check --dry-run
No changes detected

python manage.py migrate --check
No unapplied migrations

npm run check
TypeScript, ESLint, and Prettier passed

npm run build
Vite production build passed (21 modules transformed)

npx playwright test
25 passed, 2 environment-gated authenticated scenarios skipped

LOCAL_RECRUITER_BOOTSTRAP_URL=<one-time synthetic URL> npx playwright test tests/browser/recruiter/authenticated-local.spec.ts
1 passed

LOCAL_CANDIDATE_BOOTSTRAP_URL=<one-time synthetic URL> LOCAL_APPLICATION_RECRUITER_BOOTSTRAP_URL=<one-time synthetic URL> npx playwright test tests/browser/candidate/authenticated-application.spec.ts
1 passed

git diff --check
Passed
```
