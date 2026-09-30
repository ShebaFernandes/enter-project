# US6 application and candidate-progress evidence

Verified 2026-09-30 with synthetic data only.

## Application boundaries

- One verified candidate identity reused one candidate-controlled profile while each active opening produced an independent application with its own answers, consent context, timestamps, preferences, status, and immutable history.
- Submission required an open tenant-owned opening, a clean candidate-owned resume, current role-specific consent, and an idempotency key. Duplicate opening/profile submissions returned the existing application without creating a second record.
- Candidate withdrawal changed only the selected application to `WITHDRAWN`, required explicit confirmation and a current ETag, and retained the full application history.
- Sourced candidate-work records were optional links; application submission never fabricated one and never merged or overwrote an existing record.

## Status and notification controls

- Candidate-facing status was limited in services and database constraints to `APPLIED`, `PROFILE_VIEWED`, `SHORTLISTED`, `RECRUITER_INTERESTED`, `INTERVIEW_REQUESTED`, `OFFER_MADE`, `NOT_SELECTED`, and `WITHDRAWN`.
- Recruiter internal status preview produced a nullable suggestion. Publication required a current, actor-bound preview, an explicitly selected approved candidate status, explicit confirmation, a current ETag, and an idempotency key.
- Unmapped internal statuses produced no automatic candidate update. Internal status values were not returned by candidate progress APIs.
- Delivery state projection exposed only `PENDING`, `SENT`, `FAILED`, or `CANCELLED`; queued and sending states mapped to `PENDING`. Notification failures left the committed candidate status visible with a safe failed delivery state.

## Authorization, privacy, and audit

- Candidate APIs resolved the verified session identity and returned only applications owned by that candidate profile.
- Recruiter status actions required tenant membership, recruiter/hiring-manager role, application purpose, current application consent, field scope, and object ownership.
- PostgreSQL RLS tests used restricted roles to prove candidate ownership and tenant isolation for applications, status history, previews, and notification records.
- Application, consent, withdrawal, preview, publication, preference, and notification actions emitted redacted audit events containing field names and identifiers but no answer, destination, or message values.
- `SHORT_TENURE` remained informational and was absent from all application eligibility, status, score, notification, and outcome paths.

## Browser verification

- The candidate journey used a one-time local/test-only synthetic session to review a public role, submit with a scanned resume and role-specific consent, observe initial `APPLIED`, receive recruiter-confirmed `SHORTLISTED`, see `EMAIL: pending`, sign out, and receive `403` on protected API reuse.
- The recruiter journey used independent one-time synthetic sessions to verify deterministic search, authorized candidate details, neutral `SHORT_TENURE` evidence, status preview/publication, sign-out, and Back-button protection.
- Static browser coverage verified required-field validation, duplicate-safe feedback, all eight progress labels, candidate-safe delivery labels, keyboard use, 320px reflow, refresh persistence, and accessibility scans.

## Commands and results

```text
docker compose exec -T web /opt/enter-venv/bin/pytest -q
215 passed, 1 skipped (audit-tamper fixture intentionally blocked by the database trigger)

docker compose exec -T web /opt/enter-venv/bin/mypy .
Success: no issues found in 176 source files

docker compose exec -T web /opt/enter-venv/bin/ruff format --check .
176 files already formatted

docker compose exec -T web /opt/enter-venv/bin/ruff check .
All checks passed

docker compose exec -T web /opt/enter-venv/bin/python manage.py check
System check identified no issues

docker compose exec -T web /opt/enter-venv/bin/python manage.py makemigrations --check --dry-run
No changes detected

npm run check
TypeScript, ESLint, and Prettier passed

npm run build
Vite production build passed (17 modules)

npm run test:browser
26 passed, including authenticated candidate and recruiter journeys
```
