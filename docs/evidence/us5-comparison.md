# US5 deterministic candidate comparison evidence

Verified 2026-10-01 with synthetic data only. Scope is Phase 8 tasks T141–T148.

## Authorization and data flow

- A recruiter selects two to ten candidates only from the current authorized search result context. The browser stores candidate identifiers and context only, never candidate evidence.
- Every comparison request revalidates tenant membership, recruiter or scoped hiring-manager permission, search ownership or permitted opening, the current visibility rule, its attached active consent, purpose, audience, and field scope.
- Candidates that have become hidden, withdrawn consent, left the permitted context, or otherwise become unauthorized are omitted. The selection is updated and the recruiter receives an explicit stale-selection message.
- Comparison is a read-only projection. It does not create or modify `Application`, `CandidateWorkRecord`, shortlist, internal-status, or candidate-facing status records. It emits only a minimized comparison-view audit event.
- The fixed projection order is name, location, experience, notice or availability, compensation availability, skills, employment, preferences, match evidence, and informational findings. Stored match evidence is filtered again against the current consent field scope.

## Evidence, unknowns, and automation boundaries

- Each field is explicitly `KNOWN`, `UNKNOWN`, or `UNAVAILABLE`; unknown data is not inferred or fabricated. Compensation is represented only as availability, never as a disclosed value.
- Skills, employment, preferences, and search-match facts retain deterministic provenance. Current-consent narrowing cannot be broadened by another consent for a different audience.
- `SHORT_TENURE` is displayed as an informational finding with its evidence and an explicit non-interference statement. Boundary tests prove it does not change candidate order, score, or recruiting state.
- The response contains no generated comparison summary, recommendation, “best candidate,” protected attribute, automated rejection, score, or ranking.

## Accessibility and responsive behavior

- Selection, removal, comparison opening, stale-selection handling, and return-to-results focus are keyboard operable.
- The comparison uses consistent responsive cards, explicit empty/degraded guidance, accessible status announcements, and labeled informational findings.
- Browser coverage verifies 320 CSS pixel reflow, 200% zoom, focus restoration, keyboard behavior, and no serious or critical automated accessibility violations.

## Commands and results

```text
DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgresql://enter:enter@127.0.0.1:5432/enter VALKEY_URL=redis://127.0.0.1:6379/0 uv run pytest -q
248 passed, 1 skipped (the PostgreSQL trigger intentionally prevents constructing the audit-tampering fixture)

uv run pytest --collect-only -q
249 tests collected

uv run mypy .
Success: no issues found in 196 source files

uv run ruff format --check .
196 files already formatted

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
Vite production build passed (22 modules transformed)

npx playwright test
28 passed, 3 environment-gated authenticated scenarios skipped

LOCAL_RECRUITER_BOOTSTRAP_URL=<one-time synthetic URL> npx playwright test tests/browser/recruiter/authenticated-comparison.spec.ts
1 passed

LOCAL_RECRUITER_BOOTSTRAP_URL=<one-time synthetic URL> npx playwright test tests/browser/recruiter/authenticated-local.spec.ts
1 passed

git diff --check
Passed
```

No tests were deleted, repository-wide mypy coverage remains `mypy .`, no Phase 8 migration was required, and the original HTML mockup is unchanged.
