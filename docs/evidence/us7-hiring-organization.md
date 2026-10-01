# US7 hiring organization and governance evidence

Verified 2026-10-01 with synthetic data only. Scope is Phase 9 tasks T149–T163.

## Saved searches and organization administration

- Named saved searches remain separate from the six-item recent-search history and are owned by the current tenant member. The server snapshots result context and detects opening-state, opening-version, result-set, and candidate-status changes when a search is reopened.
- Saved-search input rejects undeclared properties, including a top-level `opening_id`. Opening linkage is read only from the authoritative search `criteria.context.opening_id`; the API also returns no independent top-level opening field.
- Business-unit and opening create/update operations enforce tenant ownership, fixed-role policy, idempotency, and ETag-based stale-write rejection. Cross-tenant identifiers fail without enumeration.
- Recruiter-entered candidate records accept synthetic data only and retain the immutable `RECRUITER_ENTERED_SYNTHETIC` provenance and `Recruiter-entered synthetic record` label. Real recruiter-entered candidate data was not introduced.

## Audit access and access review

- Tenant Admin audit queries return redacted administrative metadata only. Recruiter and Hiring Manager queries are limited to their permitted activity. Allowed, denied, and failed reads each create a minimized `AUDIT_READ` event without candidate values.
- Tenant Admin does not receive candidate-content access. The authenticated governance page exposes business-unit/opening administration, redacted audit metadata, access reviews, and emergency metadata, but does not render recruiter-only synthetic-candidate or saved-search controls.
- Periodic review population covers `MEMBERSHIP`, `PRIVILEGED_ROLE`, `PURPOSE_GRANT`, `EMERGENCY_GRANT`, and `AUDIT_ACCESS`, snapshots evidence, assigns an independent reviewer, avoids duplicate open reviews, and emits minimized `access_review.due.v1` events.
- Review completion records retain/revoke/exception decisions, findings, remediation state, and revocation evidence. Revocations take effect for memberships, purpose grants, and emergency grants. Exceptions require an owner and future expiry; expired exceptions revoke access, and overdue reviews escalate.
- Review completion and organization mutation use optimistic concurrency. The UI sends the current strong ETag and presents stale-review feedback instead of overwriting newer decisions.
- Emergency-access presentation contains only reason code, operation and field scopes, object count, status, and expiry. Tenant Admin can revoke an active grant without receiving candidate content.

## Tenant isolation, accessibility, and preservation

- PostgreSQL forced row-level security covers access-review and review-item tables. Service and API tests cover same-tenant authorization, least privilege, reviewer independence, non-enumeration, and negative candidate-content access.
- Recruiter and Tenant Admin interfaces are keyboard operable, responsive at 320 CSS pixels and 200% zoom, and have no serious or critical automated accessibility violations.
- Candidate-controlled profiles, separate Application/CandidateWork records, the eight-value candidate-facing status model, deterministic comparison, informational-only `SHORT_TENURE`, and prior search/interpretation behavior are unchanged.
- No previous test file was deleted. Repository-wide mypy scope was not narrowed. The original HTML mockup is unchanged.

## Commands and results

```text
DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgresql://enter:enter@127.0.0.1:5432/enter VALKEY_URL=redis://127.0.0.1:6379/0 uv run pytest -q
268 passed, 1 skipped (the PostgreSQL trigger intentionally prevents constructing the audit-tampering fixture)

uv run pytest --collect-only -q
269 tests collected

uv run mypy .
Success: no issues found in 211 source files

uv run ruff format .
211 files left unchanged

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
Vite production build passed (25 modules transformed)

npx playwright test
32 passed, 5 environment-gated authenticated scenarios skipped

LOCAL_TENANT_ADMIN_BOOTSTRAP_URL=<one-time synthetic URL> LOCAL_ORGANIZATION_RECRUITER_BOOTSTRAP_URL=<one-time synthetic URL> npx playwright test tests/browser/admin/authenticated-governance.spec.ts
2 passed

git diff --check
Passed

git diff --diff-filter=D --name-only -- app/tests
No deleted tests

git diff --quiet -- enter_recruiter_recruiter_candidate_ux.html
Original mockup unchanged
```
