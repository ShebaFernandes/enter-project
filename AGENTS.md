# Repository Guidelines

> Whatever actions you can perform yourself, do them yourself. This includes starting applications and running verification.

## Project Structure & Module Organization

The application lives in `app/`. Django configuration is in `app/config/`; domain modules are under `app/modules/`. React and Tailwind code is in `app/frontend/react/`, with server fallbacks in `app/frontend/templates/`. Tests live in `app/tests/`, including Playwright under `app/tests/browser/`. Product artifacts are in `specs/001-recruiter-candidate-workflows/`, infrastructure in `infra/`, and evidence in `docs/evidence/`. Preserve `enter_recruiter_recruiter_candidate_ux.html` unchanged.

## Build, Test, and Development Commands

- `make bootstrap`: install locked dependencies and build frontend bundles.
- `make services`: start PostgreSQL, Valkey, LocalStack S3, Mailpit, and the resume scanner.
- `make migrate && make fixtures`: apply migrations and load labeled synthetic data.
- `make dev`: run the Django web and worker containers.
- `make check`: run Ruff, formatting, mypy, TypeScript, ESLint, and Prettier checks.
- `make test`: run pytest with branch coverage.
- `make test-contract`, `make test-browser`, `make test-security`: run focused contract, Playwright, and security suites.

## Coding Style & Naming Conventions

Use four spaces and `snake_case` for Python; use `PascalCase` for classes. Ruff enforces Python 3.13 rules and a 100-character line limit. Format TypeScript, TSX, CSS, and configuration with Prettier; use `PascalCase` React components, `camelCase` functions/props, and kebab-case frontend filenames. Keep authorization, consent, tenant isolation, and disclosure decisions in backend services—not browser state.

Use `@phosphor-icons/react` for UI icons. Avoid emojis, custom SVGs, and other icon libraries when Phosphor has an equivalent. Label icon-only controls; mark decorative icons `aria-hidden="true"`.

## Visual Assets

Store original illustrations in `assets/illustrations/` with descriptive kebab-case names and import them through Vite. Do not use stock imagery. Confirm each asset's purpose, placement, aspect ratio, and rendered size before generation. Keep decorative images accessible with empty alt text, and never replace logos, Phosphor icons, or functional controls with images.

## Testing Guidelines

Name Python tests `test_*.py` and Playwright files `*.spec.ts`. Add tests beside the relevant workflow, including denial and cross-tenant cases for sensitive changes. Use markers `postgres`, `contract`, and `security` where applicable. For visual changes, test keyboard access and widths from 320 px upward; update snapshots only intentionally.

## Commit & Pull Request Guidelines

Write concise imperative commit subjects, optionally using scoped Conventional Commits such as `feat(frontend): ...`. Keep commits focused. Pull requests should explain behavior and risks, link the spec/task, list verification, and include UI screenshots. Never commit secrets, real candidate data, build output, or unrelated changes.
