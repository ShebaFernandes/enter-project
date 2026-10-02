# Pre-FM8 stabilization gate

Date: 2026-10-02

Scope: Correct the repository, dependency-security, build and documentation findings discovered
after FM7. No FM8 implementation or production route activation is included.

## Changes

- Updated the directly used Cognito JWT dependency from PyJWT 2.13.0 to 2.15.0 and refreshed the
  frozen lock.
- Replaced runtime `assert` statements in application, disclosure, note and workflow-handoff paths
  with explicit validation or fail-closed handling.
- Documented narrow Bandit exclusions for fixed migration identifiers and the non-secret LocalStack
  credential.
- Added one ordered `build:all` command. The legacy build runs first and the React build last so the
  default Vite output cleanup cannot remove the React bundle.
- Made browser CI compile all frontend bundles before Playwright.
- Added a pinned Node 22 frontend-builder stage and copied its compiled bundles into the runtime
  Docker image.
- Marked local SQLite artifacts as untracked development state and corrected stale FM7/project
  status documentation.
- Added explicit FM8 requirement traceability before FM8-01 begins.

## Verification

- PostgreSQL suite: 353 passed, 1 intentional audit-trigger skip.
- Playwright fixture/browser suite: 75 passed, 15 authenticated environment-gated tests skipped.
  FM7's accepted authenticated evidence remains 90 passed; no authenticated claim is inferred from
  this fixture-only rerun.
- Repository-wide mypy: 233 source files, no issues.
- Ruff format/lint, Django system check and migration drift: passed.
- TypeScript, ESLint, Prettier and ordered legacy/WIP/showcase/React builds: passed.
- Bandit: passed with only documented fixed-input/local-test exclusions.
- pip-audit and npm audit: no known vulnerabilities.
- Dockerfile check, Compose configuration, frontend builder stage and complete runtime image build:
  passed.
- Immutable mockup SHA-256 remains
  `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`.

FM8 may begin at FM8-01 after this stabilization change is reviewed and committed. This is a
development-phase gate, not production approval; FM9-FM14 and Phase 10 remain outstanding.
