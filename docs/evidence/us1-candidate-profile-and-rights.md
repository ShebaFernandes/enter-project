# US1 Candidate Profile and Privacy Rights Evidence

Date: 2026-09-29  
Scope: Phase 3 tasks T052-T075, T200, and T201 only.

## Test-first record

The focused tests were introduced before or alongside their implementations. During the red phase,
the candidate browser suite exposed missing responsive selectors and deletion-dialog semantics; the
privacy suite exposed export rate-limit routing, deletion-ledger byte handling, legal-hold fixture,
and retention-expiry behavior defects. The final UI pass also exposed missing stale-write
reconciliation, export-download, support-escalation, and resume-state presentation. Each failure was
corrected within Phase 3 and rerun before the complete suite.

## Final automated evidence

### PostgreSQL, RLS, Valkey, and local S3 integration

Command:

```text
DATABASE_URL=postgresql://enter:enter@127.0.0.1:5432/enter \
VALKEY_URL=redis://127.0.0.1:6379/0 \
S3_ENDPOINT_URL=http://localhost:4566 \
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
.venv/bin/pytest --ds=config.settings.local -q
```

Result: `138 passed, 1 skipped in 5.58s`.

The single skip is intentional: PostgreSQL's immutable audit trigger prevents the test from first
constructing the tampered fixture (`tests/security/test_audit_controls.py:99`). The trigger behavior
is itself the security control under test. Candidate-owner PostgreSQL RLS, negative cross-candidate
access, rights APIs, employment correction events, retention, deletion holds, and rate limits ran in
this suite.

### Browser and original-mockup regression

Command: `npm run test:browser`

Result: `12 passed`. Coverage includes 320px/375px/768px/1024px/1440px mockup baselines, 200% zoom,
keyboard focus, profile editing, HTTP 409 reconciliation, deletion confirmation, export download,
support escalation, and resume clean/partial/parse-failure/scan-rejection states.

### Static validation

Commands and results:

- `.venv/bin/ruff format --check .` — passed; 124 files formatted.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/mypy config modules` — passed; 97 source files checked.
- `npm run check` — TypeScript, ESLint, and Prettier passed.
- `npm run build` — Vite production assets built successfully.
- `.venv/bin/python manage.py check --settings=config.settings.local` — no issues.
- `.venv/bin/python manage.py makemigrations --check --dry-run --settings=config.settings.local`
  — no model changes detected.

### Container validation

Commands:

```text
docker compose up -d --build
docker compose exec -T s3-local awslocal s3api head-bucket --bucket enter-resume-quarantine
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py check --settings=config.settings.local
docker compose exec -T web python manage.py makemigrations --check --dry-run --settings=config.settings.local
```

Results: PostgreSQL and LocalStack healthy; the quarantine bucket exists in `ap-south-1`; all
candidate/privacy migrations are applied; Django checks pass; no unapplied model changes exist; web
and worker containers remain running.

## Manual browser verification

The running Django pages at `/candidate/profile/` and `/candidate/rights/` were inspected through the
browser accessibility tree and rendered screenshot. Verified headings, labels, employment and
visibility groups, live regions, profile/rights navigation, keyboard-reachable actions, and the
step-up deletion dialog. Opening and dismissing the deletion dialog caused no data mutation.

## Scope safeguards

- The original `enter_recruiter_recruiter_candidate_ux.html` was not modified.
- No Phase 4 recruiter search, criteria interpretation, application workflow, AI, embeddings, RAG,
  LangGraph, LangSmith, recruiter-facing SHORT_TENURE evaluation, or AWS deployment was implemented.
- `profile.employment_history_changed.v1` is the minimized recalculation boundary; it contains only
  profile/record IDs, versions, and changed-field metadata.
- Test records use synthetic identities and candidate data only.
