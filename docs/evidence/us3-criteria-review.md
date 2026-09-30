# US3 Criteria Review Evidence

Date: 2026-09-30  
Scope: Phase 5 tasks T095–T105 only

## Implemented boundary

- Recruiter and Hiring Manager access reuses the existing authenticated tenant membership gate.
- `/api/v1/tenants/{tenantId}/searches/interpret` returns versioned, allowlisted criteria with stable group and criterion IDs, explicit `ANY|ALL` operators, ambiguity state, deterministic estimated count, and per-group alternate-operator impact.
- Recruiter-edited criteria are revalidated by the same endpoint and are authoritative when passed to the existing `POST /searches` execution contract. The model cannot execute a search or grant access.
- Estimated counts start from the existing consent-, visibility-, field-scope-, purpose-, object-, and tenant-authorized queryset. Unauthorized candidates are not fetched and removed afterward.
- Search interpretation checkpoints are encrypted in PostgreSQL, scoped to the exact actor and tenant, protected by forced RLS, and contain only stable IDs and hashes. Raw prompts and candidate data are absent. Review checkpoints expire after 30 days; completed checkpoints expire after seven days.
- The Bedrock adapter permits only `ap-south-1`, denies cross-region inference profiles, uses bounded timeouts and one schema-repair attempt, and logs hashes rather than prompt/output bodies.
- LangGraph is limited to parse and validate before the recruiter review interrupt. Timeout, no-model, and schema-invalid cases preserve the original prompt and require deterministic manual review.
- LangSmith can be enabled only outside production when the environment explicitly asserts synthetic or irreversibly de-identified inputs. Prompt bodies remain disabled, and production is always off.

## Acceptance evidence

- Stable IDs survive recruiter edits; missing, duplicate, and cross-submission group references fail validation.
- Requirement, preference, and exclusion groups accept only `ANY|ALL`; protected fields and prompt-injection output are rejected.
- Clear and ambiguous synthetic prompts, Bedrock timeout, invalid output with one repair, and absent-model fallback are covered.
- Deterministic counts are repeatable for the same authorized corpus and update when group semantics or criteria change.
- The review UI exposes the original prompt, stable IDs, group membership, purposes, `ANY|ALL` help, estimated impact, errors, and explicit confirmation.
- Keyboard interaction, 320 CSS-pixel reflow, and automated serious/critical accessibility checks pass.
- The authenticated local recruiter journey covers ambiguous review, confirmed execution, deterministic search, candidate detail, informational `SHORT_TENURE`, sign-out, and protected history.
- `SHORT_TENURE` remains a post-ranking informational projection and is not read by the interpretation, estimate, eligibility, score, rank, recommendation, status, visibility, or outcome paths.

## Verification results

- Complete PostgreSQL suite: `184 passed, 1 skipped`. The single expected skip is the audit-tampering fixture that PostgreSQL correctly prevents from being constructed.
- Phase 5 focused Python and PostgreSQL RLS suite: `20 passed`.
- Repository mypy: success across `163 source files`.
- Ruff format: `163 files already formatted`; Ruff lint: all checks passed.
- TypeScript, ESLint, and Prettier: passed.
- Vite production build: passed; 14 modules transformed.
- Django system check: no issues. Migration drift check: no changes detected.
- Migration `operations.0003_workflowrun` applied successfully to PostgreSQL.
- Complete Playwright/accessibility suite with a one-time synthetic authenticated recruiter: `23 passed`.
- Manual DOM-assisted browser inspection confirmed the local-only authenticated recruiter workspace, labelled prompt/context/criteria controls, signed-in role projection, and responsive review semantics. The complete interaction path is additionally covered by the authenticated Playwright test.

No real candidate data, credentials, production model invocation, or production LangSmith trace was used. A promoted Bedrock model remains intentionally unconfigured locally; deterministic manual review is the required safe fallback.
