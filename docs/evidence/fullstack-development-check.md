# Full-stack development verification — 2026-10-05

The local platform runs at http://localhost:8000. This check covers development workflows using synthetic identities and data. It does not complete the 36 unchecked Phase 10 production-hardening tasks.

## Repairs

- Corrected PostgreSQL test configuration. SQLite could not run the publication migration because public jobs require PostgreSQL row-level security. Django creates a separate test database; security policies were retained.
- Fixed backend typing, imports and formatting without discarding the pre-existing frontend, resume, search and profile changes.
- Connected the development worker to employment-finding evaluation, privacy export generation, export expiry, confirmed due deletion requests, and local email delivery with retry backoff. Failed exports now surface a failure state. Deletion retains the existing deadline, confirmation and legal-hold checks.
- Rechecked application notification preferences immediately before delivery, cancelling queued notifications when permission was withdrawn.
- Fixed logout in both renderers. Redirecting to the login endpoint immediately reauthenticated a synthetic local user; successful logout now returns to `/`. Failed legacy logout keeps the page and exposes a retryable error. Real authenticated logout tests no longer mock the login endpoint.
- Corrected development startup: bootstrap preserves an existing `.env`, builds assets, migrations/fixtures use the container configuration, and `make dev` starts the worker as well as web. The example environment enables the reviewed local React routes.
- Updated CI to provide PostgreSQL and built frontend assets for backend route checks, and to type-check the complete Python source/test scope.
- Reconciled browser expectations with the existing resume-first profile, expandable criteria, candidate detail tabs, widened result workspace and shared typography. Refreshed affected visual baselines after reviewing representative rendered pages. The original HTML prototype was not edited; its formerly missing logo now loads from the existing local asset.

## Verification

| Check | Result |
| --- | --- |
| Full PostgreSQL backend suite | 405 passed, 4 skipped |
| Live resume integration in the Docker network | 6 passed, including real PDF, DOCX and scanned-PDF OCR through S3 and ClamAV |
| Default browser inventory | 114 runnable scenarios verified across the full run and targeted reruns; 21 environment-gated scenarios |
| Authenticated React workflows | 9 passed across the main run and discovery rerun |
| Authenticated legacy workflows | 8 passed across the legacy and logout runs |
| Python lint / formatting | Passed; 250 source files formatted |
| Full mypy check | Passed; 250 source files |
| TypeScript / ESLint / Prettier | Passed |
| All four Vite builds | Passed |
| Bandit | Passed; existing stale suppression warnings remain |
| Running Django system check | Passed |
| Migration drift | No changes detected |
| Local service health | Web/worker running; PostgreSQL, S3 and ClamAV healthy |
| HTTP smoke check | `/health/`, `/`, `/jobs/`, `/candidate/profile/` returned 200 |

Three backend skips require real S3/ClamAV and were separately executed successfully inside the web container. The fourth is the intentional audit-tampering test: the PostgreSQL trigger prevents creating its corrupt fixture.

The final broad browser run passed 113 scenarios and exposed one remaining stale logout URL expectation. That expectation was corrected to the public chooser, and the fixture now waits for navigation completion before checking storage. The focused rerun passed and additionally checks failed logout, retry, session-storage clearing and absence of an automatic login request. Earlier, a 375px prototype screenshot differed by 97 pixels; all six prototype screenshots passed unchanged on a serial rerun. No visual tolerance was widened.

Authenticated coverage includes candidate profile save/publication, application submission and status tracking, privacy actions, recruiter search/filter/review/pagination, authorized details, notes and stale-write reconciliation, candidate comparison, public opening publication/withdrawal, tenant organization, redacted governance and logout. The phase-only FM1 capture utility, FM3 live capture and FM5 intermediate-cutover configuration were not rerun; their underlying final-state routes have other coverage. This is not a manual screen-reader or production capacity assessment.

## Reproduction and isolation

Run the normal local workflow from the repository root:

```sh
make bootstrap
make services
make migrate
make fixtures
make dev
```

In a separate terminal:

```sh
make check
make test
make test-contract
make test-browser
```

The verification used `config.settings.test` for PostgreSQL backend tests. Authenticated browser checks used synthetic database `enter_fm4_verify_fullstack_20261005`, Valkey database 11, a React server on port 8017 and a legacy server on port 8018. Bootstrap commands and servers used the same database/cache settings. Local browser origin flags in `tests/browser/local-bootstrap.ts` enable the relevant authenticated scenarios; running the default browser command alone intentionally skips them.

The Docker resume check used `RUN_RESUME_LIVE=1`, `APP_ENV=test`, and `DJANGO_SETTINGS_MODULE=config.settings.test` with `pytest tests/integration/candidate/test_resume_processing.py`. Test dependencies were installed temporarily in the local web container; they are not added to the production image.

## Remaining boundaries

Production deployment, cloud infrastructure/recovery exercises, external identity/provider configuration, independent security review, legal/privacy approval, manual accessibility and load testing remain outstanding in `specs/001-recruiter-candidate-workflows/tasks.md`. WhatsApp and unapproved AI-dependent features remain disabled. The development worker explicitly rejects production operation and routes email only to the local mail sink; it is not a production queue/provider implementation.

The two temporary verification servers were stopped; the normal application and worker remain running. The isolated synthetic verification database is retained. Incoming uncommitted work was preserved. No deployment or git commit was made, and `.env` secrets were not printed or changed.
