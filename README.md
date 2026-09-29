# Enter — Recruiter and Candidate Workflows

Enter is an India-first recruiting platform for candidates, recruiters, hiring managers, tenant administrators, and platform security administrators. It is being developed from an existing single-file UX prototype into a production-oriented Django application with privacy, accessibility, tenant isolation, and human-controlled hiring decisions built into its design.

## Current status

The specification, architecture, and implementation backlog are complete. Implementation Phases 1–3 are complete: the project foundation, shared security and tenancy layer, and the candidate profile/privacy-rights MVP are implemented and tested. The original HTML prototype remains unchanged as the regression baseline.

| Area | Status |
|---|---|
| UX prototype | Available as a read-only baseline |
| Project constitution | Ratified (v1.0.0) |
| Feature specification | Approved |
| Requirements quality review | Passed |
| Architecture and technical research | Completed |
| Data model | Designed |
| API, event, authorization, and AI contracts | Defined |
| Implementation plan and task backlog | Completed |
| Application foundation | Complete |
| Security, tenancy, identity, and opening foundation | Complete |
| Candidate profile and privacy-rights MVP | Complete |
| Recruiter search and intent review | Not started |
| Applications and candidate progress | Not started |
| Recruiter evaluation and shortlist workflows | Not started |
| Production deployment | Not started |

## Implemented so far

### Project and development foundation

- Django 5.2 modular-monolith backend with Django REST Framework.
- Server-rendered HTML with framework-free TypeScript, Vite, and responsive CSS.
- Reproducible Python and Node dependency locks, non-root web/worker containers, and environment validation.
- Local PostgreSQL 16 with `pgvector`, Valkey, LocalStack S3, and Mailpit services through Docker Compose.
- CI and local commands for linting, formatting, type checking, contract tests, browser/accessibility tests, security scanning, dependency auditing, and SBOM generation.
- Preserved UX prototype with Playwright visual baselines at 320, 375, 768, 1024, and 1440 CSS pixels and at 200% zoom.

### Security, identity, tenancy, and operations

- Cognito OIDC/PKCE identity flow with verified-email handling, workforce federation boundaries, MFA assurance, rotating sessions, revocation, and global sign-out.
- Deny-by-default authorization across role, purpose, tenant, object, field, consent, and explicit access grants.
- PostgreSQL row-level-security context and cross-tenant isolation tests.
- Platform tenant provisioning, business-unit lifecycle, opening lifecycle, hiring-team scope, and synthetic recruiter-entered candidate records with immutable provenance.
- Purpose-scoped access grants and peer-approved, time-limited break-glass access with Tenant Admin notification.
- Immutable, minimized, hash-chained audit events and durable checkpoint support.
- Versioned field encryption, blind-index helpers, correlation IDs, RFC 9457 errors, ETags/optimistic concurrency, idempotency, transactional outbox processing, and reconciliation.
- Email notification records and delivery workers with bounded retry, duplicate suppression, callback validation, and DLQ handling. WhatsApp remains disabled pending approval.
- Identity-and-network rate limiting, temporary escalation, anomaly tightening, step-up challenges, and audited overrides without permanent automatic lockout.
- Terraform definitions for asynchronous queues/DLQs, schedules, KMS keys, secrets, and alarms.

### Candidate profile and privacy-rights MVP

- One candidate-controlled profile per verified identity, including contact details, skills, links, employment history, compensation, availability, and profile-completeness validation.
- Profile correction and publication with strong ETags and conflict reconciliation, so stale edits do not silently overwrite newer data.
- Four visibility modes: Approved recruiters, Matching roles, Applied roles only, and Not looking, with conditional consent and immediate hiding/withdrawal.
- PDF, DOC, and DOCX resume intake into quarantine with file validation, malware-scan gating, parsing states, source provenance, confidence/source spans, and manual-entry recovery. Extracted suggestions do not invent missing facts or overwrite deliberate corrections.
- Accessible candidate pages at `/candidate/profile/` and `/candidate/rights/`, including keyboard navigation, error summaries, live regions, reduced-motion support, responsive reflow, and 200% zoom support.
- A privacy-rights center for access, correction, consent withdrawal, profile hiding, export, deletion, request history, failure visibility, and support escalation.
- Authenticated privacy exports with a 24-hour completion target and expiring downloads.
- Deletion with recent subject-bound step-up, explicit consequence confirmation, immediate hiding, legal-hold and active-process retention exceptions, 30-day erasure handling, anonymized aggregates, and deletion evidence.
- Consent-renewal scheduling and retention/expiry workers, with minimized audit events throughout candidate and rights workflows.

### Verification completed

- Full PostgreSQL/RLS/Valkey/local-S3 suite: **138 passed, 1 intentional skip**.
- Playwright browser and original-mockup regression suite: **12 passed**.
- Ruff formatting/linting, mypy, TypeScript, ESLint, Prettier, Vite production build, Django system checks, and migration-drift checks passed.
- Docker Compose validation confirmed healthy PostgreSQL and LocalStack services, quarantine-bucket creation, applied migrations, and running web/worker containers.

See [US1 implementation evidence](./docs/evidence/us1-candidate-profile-and-rights.md) for the recorded commands, results, and scope safeguards.

## Planned product capabilities

### Candidate experience

- Create one candidate-controlled profile per verified email.
- Upload a PDF, DOC, or DOCX resume and review extracted fields before saving or publishing them.
- Correct profile information and prevent automated suggestions from overwriting deliberate edits.
- Choose between Approved recruiters, Matching roles, Applied roles only, and Not looking visibility.
- Apply to multiple openings while keeping answers, consent, status, and history separate for each application.
- Track applications through the canonical candidate-facing statuses: Applied, Profile viewed, Shortlisted, Recruiter interested, Interview requested, Offer made, Not selected, and Withdrawn.
- Use a self-service rights center for access, correction, consent withdrawal, profile hiding, export, and deletion requests.

### Recruiter experience

- Sign in with a verified work identity and search for candidates using natural language or structured criteria.
- Review ambiguous search interpretations, edit criteria, group conditions with `ANY` or `ALL`, and see estimated impact before searching.
- Receive ranked results with authorized evidence explaining each match.
- Review candidates, maintain tenant-scoped notes and shortlists, and manage sourced and applied candidates without merging their histories.
- Preview candidate-facing status changes and explicitly confirm publication and notification.
- Compare consistent candidate evidence without automated recommendations or hiring decisions.
- Preview and confirm minimum-data contact or sharing actions against current consent and authorization.

### Administration and governance

- Organize tenants, business units, openings, and saved searches.
- Enforce five least-privilege roles: Candidate, Recruiter, Hiring Manager, Tenant Admin, and Platform Security Admin.
- Isolate each tenant's openings, applications, notes, searches, exports, communications, and audit history.
- Support redacted audit access, periodic access reviews, and narrowly scoped, peer-approved, time-limited emergency access.
- Apply candidate retention, legal-hold, deletion, backup, incident-response, and abuse-protection policies.

## Architecture

The application is a Django 5.2 modular monolith using server-rendered templates with small TypeScript modules and Vite. PostgreSQL 16 is the transactional source of truth, with row-level security and planned full-text, `pg_trgm`, and `pgvector` search. The architecture uses Cognito for identity, S3 quarantine/clean/export storage, SQS plus a transactional outbox for background work, Valkey for ephemeral caching and rate counters, and ECS Fargate for the planned AWS deployment.

Production is planned for Mumbai (`ap-south-1`) with warm recovery infrastructure in Hyderabad (`ap-south-2`). Targets include 99.9% monthly availability, a 15-minute recovery point, a four-hour recovery time, encrypted 35-day backups, and normal search performance of three seconds or less at p95 for the expected launch load.

AI is intentionally bounded and advisory. It may suggest resume fields, interpret search text, assist semantic retrieval, and produce explanations tied to authorized evidence. It may not make authorization, eligibility, consent, status-publication, disclosure, or hiring decisions. Deterministic rules and explicit human actions remain authoritative.

## Completed project artifacts

- [UX prototype](./enter_recruiter_recruiter_candidate_ux.html) — original recruiter and candidate experience used as the preservation baseline.
- [Project constitution](./.specify/memory/constitution.md) — accessibility, privacy, responsive design, testing, simplicity, and compatibility principles.
- [Approved feature specification](./specs/001-recruiter-candidate-workflows/spec.md) — seven independently testable user stories, 61 acceptance scenarios, 65 functional requirements, edge cases, and 37 measurable outcomes.
- [Requirements checklist](./specs/001-recruiter-candidate-workflows/checklists/requirements.md) — completed specification-quality review with no unresolved clarification markers.
- [Architecture research](./specs/001-recruiter-candidate-workflows/research.md) — decisions covering the application shape, storage, identity, files, asynchronous processing, AI, AWS, security, concurrency, delivery, candidate rights, visibility, statuses, and tenant governance.
- [Implementation plan](./specs/001-recruiter-candidate-workflows/plan.md) — technical architecture, module boundaries, rollout order, security strategy, and production topology.
- [Data model](./specs/001-recruiter-candidate-workflows/data-model.md) — entities, relationships, state machines, authorization invariants, indexes, partitioning, and retention rules.
- [OpenAPI contract](./specs/001-recruiter-candidate-workflows/contracts/openapi.yaml) — versioned REST contract for candidate, recruiter, tenant, audit, rights, and emergency-access workflows.
- [Authorization matrix](./specs/001-recruiter-candidate-workflows/contracts/authorization-matrix.md) — role, tenant, object, purpose, and administrative access boundaries.
- [Event contract](./specs/001-recruiter-candidate-workflows/contracts/events.md) — asynchronous event and delivery expectations.
- [AI boundary contract](./specs/001-recruiter-candidate-workflows/contracts/ai-boundaries.md) — permitted uses, prohibited decisions, RAG sequence, model controls, and evaluation gates.
- [Planning quickstart](./specs/001-recruiter-candidate-workflows/quickstart.md) — intended local services, configuration, developer commands, test fixtures, release gates, and production-readiness criteria.
- [Implementation tasks](./specs/001-recruiter-candidate-workflows/tasks.md) — dependency-ordered backlog of 206 setup, implementation, testing, governance, and production-hardening tasks; 77 are complete through Phase 3.

## Delivery roadmap

1. ✅ Establish the repository structure, tooling, and immutable UX baseline.
2. ✅ Build identity, tenancy, authorization, auditing, shared data, and opening foundations.
3. ✅ Deliver the candidate-controlled profile and privacy-rights MVP using synthetic data.
4. Add deterministic recruiter search and search-intent review.
5. Add applications and candidate progress tracking.
6. Add recruiter candidate management, disclosures, and shortlist comparison.
7. Add saved searches, tenant governance, audit access, and access reviews.
8. Complete accessibility, privacy, security, incident-response, recovery, load, AI, and production-release evidence.

## Local development

### Prerequisites

- Python 3.13 or 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js 22–24 and npm
- Docker with Compose
- Terraform for infrastructure work

### Start the application

Install dependencies and start the supporting services:

```bash
make bootstrap
make services
make migrate
make fixtures
make dev
```

The web application is served at `http://localhost:8000`. Mailpit is available at `http://localhost:8025`, and the health check is at `http://localhost:8000/health/`.

To run validation:

```bash
make check
make test
make test-contract
make test-browser
make test-security
```

Use `make services-down` to stop local services. See the [planning quickstart](./specs/001-recruiter-candidate-workflows/quickstart.md) for the complete command set, environment details, and verification matrix.

## Launch scope and safeguards

- India-only candidate-content processing at initial launch.
- WCAG 2.2 AA and responsive support from 320 CSS pixels through desktop layouts.
- Synthetic data only until legal, privacy, accessibility, security, incident, access-review, backup, recovery, and production-readiness gates pass.
- Real recruiter-entered candidate records are deferred pending a separate specification and privacy review.
- WhatsApp delivery stays disabled until its provider, residency, templates, consent, and callbacks are approved.
- AI-dependent enhancements remain feature-flagged off until their quality, privacy, fairness, latency, cost, and residency evaluations pass.

## Remaining external preconditions

Before production implementation can be promoted, the project still requires legal and privacy approval, production AWS and domain setup, designated security approvers, a WhatsApp launch decision, in-region model evaluation, and pilot-tenant identity and support details.
