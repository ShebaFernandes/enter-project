# US2 deterministic recruiter-search evidence

Verified 2026-09-30 with synthetic data only.

## Fixed corpus and authorization

- `AD_HOC` returned only published `APPROVED_RECRUITERS` profiles where both the visibility audience and current `RECRUITING_DISCOVERY` consent explicitly named the tenant.
- `OPENING` required one active, tenant-owned opening and returned `MATCHING_ROLES` profiles only after exact candidate-controlled role, location, and work-arrangement preferences matched.
- Closed, missing, foreign-tenant, `APPLIED_ROLES_ONLY`, and `NOT_LOOKING` contexts produced no discoverable candidate.
- PostgreSQL RLS tests switched to a restricted database role and proved search rows and finding evidence were unavailable without the matching tenant/search context.

## Deterministic behavior

- Requirement and exclusion groups controlled eligibility with exact `ANY`/`ALL` semantics; preference groups affected ordering only.
- Protected/proxy fields were rejected, unknown values were disclosed, ties were ordered by candidate ID, and authorization predicates ran before ranking.
- Search queries use a 2.5-second PostgreSQL statement timeout and return a typed-search-safe `503` state on database degradation.

## SHORT_TENURE corpus

- Completed permanent 8-month role: one informational `FOUND` evaluation.
- Completed permanent 12-month role and current 8-month role: no warning.
- Internship, apprenticeship, fixed-term, consulting, seasonal, and other temporary work: excluded.
- Missing, ambiguous, non-day-precision, reversed, or unconfirmed dates: `INSUFFICIENT_DATA`, never a warning.
- Candidate corrections superseded the obsolete evaluation; multiple qualifying records retained separate findings.
- Tests confirmed evaluation did not mutate profile visibility/version and never fed eligibility, score, rank, recommendation, application status, or hiring outcome.

## Browser and speech evidence

- Playwright covered prompt/criteria persistence, loading, empty, safe error, results, filters, candidate details, keyboard focus, 320px layout, sign-out/history protection, and neutral finding evidence.
- Web Speech covered unsupported fallback, listening, transcribing, ready, editable transcript, stopping, and no automatic submission. Typed search remained available on every path.
- Axe found no violations in the recruiter search error-state fixture.

## Commands and results

```text
PostgreSQL full suite: 164 passed, 1 skipped (tamper fixture intentionally prevented by immutable trigger)
SQLite portability suite: 157 passed, 8 PostgreSQL-only skipped
Recruiter Playwright suite: 7 passed
Full Playwright suite: 19 passed
Ruff: passed
TypeScript, ESLint, Prettier: passed
Vite production build: passed
Django system check: passed
Migration drift check: passed
Focused Phase 4 mypy: passed
```
