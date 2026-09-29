# Enter — Recruiter and Candidate Workflows

Enter is a planned production-ready recruiting platform for candidates, recruiters, hiring managers, tenant administrators, and platform security administrators. The project is evolving an existing single-file UX prototype into an India-first web application with privacy, accessibility, tenant isolation, and human-controlled hiring decisions built into its design.

## Current status

The project has completed specification and implementation planning. The Phase 1 setup and a deliberately bounded portion of the Phase 2 security/tenant/opening foundation are now implemented. The existing HTML prototype remains unchanged as the visual and functional baseline; candidate workflows, search, applications, AI, communications, and AWS deployment have not started.

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
| Application implementation | Phase 1–2 foundation in progress |
| Production deployment | Not started |

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

## Architecture decided so far

The planned implementation is a Django 5.2 modular monolith using server-rendered templates with small TypeScript 5 modules and Vite. PostgreSQL 16 is the transactional source of truth, with row-level security, full-text search, `pg_trgm`, and `pgvector`. The design also uses Cognito for identity, S3 quarantine/clean/export storage, SQS and an outbox for background work, Valkey for ephemeral caching and rate counters, and ECS Fargate on AWS.

Production is planned for Mumbai (`ap-south-1`) with warm recovery infrastructure in Hyderabad (`ap-south-2`). Targets include 99.9% monthly availability, a 15-minute recovery point, a four-hour recovery time, encrypted 35-day backups, and normal search performance of three seconds or less at p95 for the expected launch load.

AI is intentionally bounded and advisory. It may suggest resume fields, interpret search text, assist semantic retrieval, and produce explanations tied to authorized evidence. It may not make authorization, eligibility, consent, status-publication, disclosure, or hiring decisions. Deterministic rules and explicit human actions remain authoritative.

## Completed project artifacts

- [UX prototype](./enter_recruiter_recruiter_candidate_ux.html) — original recruiter and candidate experience used as the preservation baseline.
- [Project constitution](./.specify/memory/constitution.md) — accessibility, privacy, responsive design, testing, simplicity, and compatibility principles.
- [Approved feature specification](./specs/001-recruiter-candidate-workflows/spec.md) — seven independently testable user stories, 48 acceptance scenarios, 100 requirements, edge cases, and 36 measurable outcomes.
- [Requirements checklist](./specs/001-recruiter-candidate-workflows/checklists/requirements.md) — completed specification-quality review with no unresolved clarification markers.
- [Architecture research](./specs/001-recruiter-candidate-workflows/research.md) — decisions covering the application shape, storage, identity, files, asynchronous processing, AI, AWS, security, concurrency, delivery, candidate rights, visibility, statuses, and tenant governance.
- [Implementation plan](./specs/001-recruiter-candidate-workflows/plan.md) — technical architecture, module boundaries, rollout order, security strategy, and production topology.
- [Data model](./specs/001-recruiter-candidate-workflows/data-model.md) — entities, relationships, state machines, authorization invariants, indexes, partitioning, and retention rules.
- [OpenAPI contract](./specs/001-recruiter-candidate-workflows/contracts/openapi.yaml) — versioned REST contract for candidate, recruiter, tenant, audit, rights, and emergency-access workflows.
- [Authorization matrix](./specs/001-recruiter-candidate-workflows/contracts/authorization-matrix.md) — role, tenant, object, purpose, and administrative access boundaries.
- [Event contract](./specs/001-recruiter-candidate-workflows/contracts/events.md) — asynchronous event and delivery expectations.
- [AI boundary contract](./specs/001-recruiter-candidate-workflows/contracts/ai-boundaries.md) — permitted uses, prohibited decisions, RAG sequence, model controls, and evaluation gates.
- [Planning quickstart](./specs/001-recruiter-candidate-workflows/quickstart.md) — intended local services, configuration, developer commands, test fixtures, release gates, and production-readiness criteria.
- [Implementation tasks](./specs/001-recruiter-candidate-workflows/tasks.md) — dependency-ordered backlog of 199 setup, implementation, testing, governance, and production-hardening tasks.

## Delivery roadmap

1. Establish the repository structure, tooling, and immutable UX baseline.
2. Build identity, tenancy, authorization, auditing, shared data, and opening foundations.
3. Deliver the candidate-controlled profile and privacy-rights MVP using synthetic data.
4. Add deterministic recruiter search and criteria review.
5. Add applications and candidate progress tracking.
6. Add recruiter candidate management, disclosures, and shortlist comparison.
7. Add saved searches, tenant governance, audit access, and access reviews.
8. Complete accessibility, privacy, security, incident-response, recovery, load, AI, and production-release evidence.

## Planned local development

The implementation is expected to require Python 3.13, Node.js 22 LTS, PostgreSQL 16 with `pgvector` and `pg_trgm`, a Docker-compatible runtime, Terraform, and a synthetic-data-only AWS development environment.

The local command interface is available:

```bash
make bootstrap
make services
make migrate
make fixtures
make dev
make check
make test
```

See the [planning quickstart](./specs/001-recruiter-candidate-workflows/quickstart.md) for the complete intended command set and verification matrix.

## Launch scope and safeguards

- India-only candidate-content processing at initial launch.
- WCAG 2.2 AA and responsive support from 320 CSS pixels through desktop layouts.
- Synthetic data only until legal, privacy, accessibility, security, incident, access-review, backup, recovery, and production-readiness gates pass.
- Real recruiter-entered candidate records are deferred pending a separate specification and privacy review.
- WhatsApp delivery stays disabled until its provider, residency, templates, consent, and callbacks are approved.
- AI-dependent enhancements remain feature-flagged off until their quality, privacy, fairness, latency, cost, and residency evaluations pass.

## Remaining external preconditions

Before production implementation can be promoted, the project still requires legal and privacy approval, production AWS and domain setup, designated security approvers, a WhatsApp launch decision, in-region model evaluation, and pilot-tenant identity and support details.
