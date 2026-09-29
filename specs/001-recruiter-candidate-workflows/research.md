# Phase 0 Research: Recruiter and Candidate Workflows

**Date**: 2026-09-28  
**Scope**: Technical decisions required to plan the production implementation.  
**Launch boundary**: India-only production; primary region Mumbai (`ap-south-1`), recovery region Hyderabad (`ap-south-2`).

## Decision 1: Application shape

**Decision**: Build a Django 5.2 LTS modular monolith on Python 3.13. Render the existing experience with Django templates and progressively enhanced, typed ES modules compiled by Vite. Expose versioned JSON endpoints with Django REST Framework only where asynchronous interaction needs them.

**Rationale**:

- The approved mockup is already semantic HTML, CSS, and JavaScript. Server-rendered templates preserve it with the least visual and behavioral churn.
- One deployable application keeps authentication, authorization, transactions, auditing, retention, and user-visible state changes in one consistency boundary.
- Django supplies mature authentication/session integration, CSRF protection, forms, migrations, ORM transactions, admin primitives, and accessibility-friendly server rendering.
- TypeScript is limited to browser behavior that benefits from static checking; no client framework is required at launch.

**Alternatives rejected**:

- **React/Next.js SPA**: duplicates server and client state, requires hydration and a larger accessibility/regression surface, and does not solve a requirement the current mockup cannot meet.
- **FastAPI plus separate frontend**: good for API-first systems, but would require assembling more authentication, form, admin, and rendering infrastructure.
- **Microservices**: add distributed transactions, tracing, operational overhead, and failure modes before team or scaling boundaries justify them.

## Decision 2: Transactional storage, tenancy, and search

**Decision**: Use PostgreSQL 16 on Amazon RDS Multi-AZ with a shared schema. Tenant-owned rows carry a non-null `tenant_id`; global candidate-owned rows do not. Enforce authorization in the service layer and PostgreSQL row-level security (RLS) as defense in depth. Use PostgreSQL full-text search, `pg_trgm`, and `pgvector` for hybrid retrieval.

**Rationale**:

- The workflows are relational and transaction-heavy: one candidate profile, separate applications, consent, status histories, notes, audit records, and idempotency all need strong consistency.
- RLS limits the blast radius of an application authorization defect. Each transaction sets verified actor, tenant, and approved access-grant context; unset context denies protected data.
- At one million profiles, PostgreSQL hybrid search is the simplest datastore that can meet the three-second p95 target if indexes, authorization filters, bounded candidate sets, and pagination are designed together and verified by load tests.
- A single database avoids dual-write consistency between the source of truth and a separate search service.

**Alternatives rejected**:

- **Database per tenant**: high migration, connection, backup, and operational overhead for 100 launch tenants.
- **Schema per tenant**: complicates migrations and global candidate-controlled profiles.
- **OpenSearch at launch**: adds a second copy of sensitive candidate data, authorization-index lag, deletion complexity, and another recovery surface. Introduce it only if production-shaped load tests prove PostgreSQL cannot meet the search SLO.
- **Bedrock Knowledge Bases as the system search**: does not replace transactional permissions, strict filters, application state, or deterministic ranking.

## Decision 3: Authentication and application sessions

**Decision**: Use Amazon Cognito user pools as the identity provider. Candidates authenticate with verified-email passwordless OTP. Recruiter-side users authenticate through tenant SAML/OIDC federation where available, with Cognito-managed MFA fallback. The Django backend acts as a confidential OIDC client and issues short-lived, secure, HttpOnly, SameSite application sessions; browser code does not retain access tokens.

**Rationale**:

- Cognito supports passwordless email OTP and workforce federation while keeping credential handling outside the application.
- Backend-for-frontend sessions reduce token exposure and fit the server-rendered architecture.
- Roles, tenant memberships, object grants, consent, and emergency approvals remain authoritative in PostgreSQL rather than mutable identity-provider claims.

**Alternatives rejected**:

- **Custom password/OTP storage**: unnecessary credential and abuse risk.
- **JWTs in localStorage**: violates the constitution's sensitive browser-storage rule and increases XSS impact.
- **Cognito groups as authorization**: cannot express tenant/object permissions, consent, or time-bound approved emergency grants safely.

## Decision 4: Files and resume processing

**Decision**: Upload directly through a short-lived presigned URL into an S3 quarantine bucket using randomized object keys. Amazon GuardDuty Malware Protection scans new objects. Bucket policy denies reads unless a clean scan tag is present. A private ECS Fargate worker then validates MIME/signature/size, parses the file in a resource-limited sandbox, writes normalized suggestions, and moves/copies the accepted object to a clean encrypted bucket. A candidate must review extracted fields before publication.

**Rationale**:

- Application containers never stream untrusted files through the web tier.
- Quarantine and clean zones make the “never expose before scanning” rule enforceable at storage policy level.
- Parsing failure can degrade safely to manual entry without blocking profile creation.

**Defaults**:

- PDF, DOC, and DOCX only; 10 MiB maximum; one active resume plus version history required for audit/deletion.
- Strip macros and active content; do not render office documents in the browser.
- Scan/parse status is explicit: `UPLOADING`, `SCANNING`, `SCAN_FAILED`, `PARSING`, `REVIEW_REQUIRED`, `READY`, or `REJECTED`.

**Alternatives rejected**:

- **Parsing in the request process**: risks resource exhaustion and makes failures block the web tier.
- **Publishing before scan completes**: directly contradicts the accepted fail-closed behavior.
- **Filename-derived extraction**: contradicts the specification and can invent candidate facts.

## Decision 5: Asynchronous work and integrations

**Decision**: Use a transactional outbox in PostgreSQL, SQS Standard queues, SQS dead-letter queues, and idempotent workers from the same codebase. EventBridge Scheduler starts recurring retention, consent-renewal, and reconciliation jobs. SES provides launch email. WhatsApp is an adapter behind an explicit-consent and approved-template boundary; until a provider is approved, the UI shows it as unavailable rather than using consumer deep links for production communications.

**Rationale**:

- The outbox commits business state and intended side effects atomically.
- Standard queues and idempotency tolerate duplicate delivery without requiring FIFO throughput or ordering everywhere.
- Internal notification delivery uses `QUEUED`, `SENDING`, `SENT`, `FAILED`, or `CANCELLED`; candidate-facing projections map `QUEUED` and `SENDING` to `PENDING` and expose only `PENDING`, `SENT`, `FAILED`, or `CANCELLED`, so bounded retries never imply delivery that did not occur.

**Defaults**:

- Five retry attempts with exponential backoff within 24 hours, then a dead-letter queue and visible terminal failure.
- Provider request uses the notification id as idempotency key where supported.
- Reconciliation alarms on outbox age, queue age, dead-letter depth, and state mismatches.

**Alternatives rejected**:

- **Celery plus self-managed Redis broker**: adds a separate scheduler and broker where SQS/EventBridge already satisfy the reliability needs.
- **Synchronous email or messaging**: external latency/failure would block core transactions and obscure committed state.

## Decision 6: AI, RAG, LangGraph, and LangSmith

**Decision**:

- Use deterministic code first for validation, permissions, strict criteria, status mapping, retention, and all writes.
- Use a provider-neutral `ModelGateway` over Amazon Bedrock in `ap-south-1`, restricted to in-region inference only. Begin evaluation with Gemma 3 12B IT for structured search-intent and extraction-assist tasks; select the smallest in-region model that passes the committed evaluation suite before launch.
- Use Amazon Titan Text Embeddings V2 at 512 dimensions for normalized evidence embeddings, stored in `pgvector`.
- Implement RAG in application code: authorize and filter first, retrieve structured facts plus bounded resume evidence, then generate an explanation with citations back to stored evidence. Do not send private notes, contact data, compensation, or unrelated application data to the model.
- Use LangGraph only for resumable, human-reviewed resume enrichment and ambiguous-query clarification. Persist checkpoints in PostgreSQL with actor/tenant/object scope and expiry. No autonomous agent may contact candidates, change status, alter consent, or broaden access.
- Use LangSmith only in non-production with synthetic or irreversibly de-identified evaluation data. Production traces use OpenTelemetry/CloudWatch and exclude prompt bodies. A future production LangSmith deployment requires a separate residency, privacy, security, and procurement approval.

**Rationale**:

- These boundaries use models where ambiguity exists without delegating authorization or hiring decisions.
- In-region Bedrock avoids cross-region inference for candidate content; Bedrock providers do not receive access to prompts/completions as model-training data under the service's documented controls.
- Application-owned RAG makes authorization filters and evidence provenance explicit.
- LangGraph is justified only where durable pause/resume and human correction are real requirements.

**Failure behavior**:

- Model unavailable/timeout: preserve the user's input, offer manual structured criteria or manual profile entry, and never weaken strict filters.
- Embedding unavailable: queue indexing; exclude the unindexed record from semantic search but retain deterministic exact/filter search and show indexing status to authorized operators.
- Low confidence or schema-invalid output: discard it, show the original input, and require correction. Retry at most once with a repair prompt.
- Citation/evidence mismatch: suppress the generated explanation and fall back to deterministic evidence labels.

**Alternatives rejected**:

- **Bedrock Agents or a general autonomous agent**: too much tool authority for a sensitive hiring workflow.
- **Model-generated ranking/status decisions**: conflicts with explainability, human review, and protected-attribute constraints.
- **APAC or global cross-region inference**: conflicts with the India-only launch boundary.
- **Raw production traces in LangSmith SaaS**: unnecessary disclosure of candidate content; masking alone is not a complete guarantee.
- **Self-hosted LangSmith at launch**: its data-plane dependencies and operations are disproportionate to two bounded workflows.

## Decision 7: AWS topology, availability, and recovery

**Decision**: Deploy the primary application to Mumbai across at least two Availability Zones: Route 53, regional WAF on an Application Load Balancer, ECS Fargate web/worker services in private subnets, RDS PostgreSQL Multi-AZ DB instance, ElastiCache Serverless (Valkey) for ephemeral caches/rate counters, S3, SQS, SES, KMS, Secrets Manager, and Bedrock private access where supported. Provision a warm recovery foundation in Hyderabad with infrastructure as code. At launch, CloudFront may serve only versioned public static assets from an origin containing no candidate or tenant data; application traffic goes directly to the Mumbai regional ALB, and authenticated routes, HTML, APIs, uploads, downloads, exports, and candidate content never use the global CDN.

**Recovery design**:

- RDS cross-region automated backups and transaction logs target Hyderabad; recovery procedures are designed and tested to the 15-minute RPO and four-hour RTO.
- S3 cross-region replication covers clean resumes and immutable audit digests. Quarantine objects are short lived and not replicated unless required by an active incident/legal hold.
- Configuration, container images, and infrastructure definitions are replicated or deployable in the recovery region.
- Backups are KMS-encrypted and retained 35 days. Quarterly exercises restore into an isolated account/VPC and test integrity, RLS, authorization, audit continuity, and replay of deletion, consent-withdrawal, tenant-access-revocation, and emergency-grant-revocation events through the recovery point before restored access is enabled.
- Recovery is active/passive. DNS failover is a controlled human action because database promotion, identity callbacks, queues, and external integrations must be reconciled together.

**Alternatives rejected**:

- **Active/active multi-region writes**: conflicts with simple transactional consistency and is unnecessary for 99.9% availability/four-hour RTO.
- **EKS/Kubernetes**: adds an orchestration platform without a workload need that Fargate cannot meet.
- **Serverless-only/Lambda web application**: possible, but long-lived web behavior, parsing workers, database pooling, and predictable Django operations are simpler on Fargate.

## Decision 8: Security, auditing, and abuse controls

**Decision**: Every backend request resolves actor, fixed role, tenant membership, object permission, candidate consent/visibility, and any purpose-bound grant before data access. Audit security-relevant reads and all mutations to an append-only application audit table; write daily hash-chain checkpoints to an S3 Object Lock compliance bucket in a separate security account. Platform Security Admin candidate access uses a time-limited, exact read-scope grant approved by a different designated Platform Security Admin after re-authentication. Activation immediately notifies affected Tenant Admins, who may revoke without gaining candidate-content access.

Audit-history reads are redacted, purpose-limited, and audited themselves. Before production and periodically thereafter, review tenant memberships, privileged roles, purpose grants, emergency grants, and audit access, recording decisions, revocations, and bounded exceptions. Candidate-data incidents follow an approved India-specific response and notification runbook that is exercised before real data.

Use WAF for coarse network/bot protection and an application limiter backed by Valkey for the specification's identity-plus-network thresholds. Rate-limit decisions use generic responses, escalating temporary delays, anomaly tightening, and audited authorized overrides; no automatic permanent lockout.

**Rationale**:

- WAF alone cannot safely aggregate all verified identity, tenant, endpoint, and network signals.
- App-level decisions can respect accessibility, support recovery, and avoid account enumeration while still preserving an immutable trail.

## Decision 9: Concurrency and consistency

**Decision**: Use optimistic concurrency with an integer `version` and HTTP `ETag`/`If-Match` for consent, visibility, application status, recruiter notes, and administrative settings. A stale update returns `409 CONFLICT` with an authorized current representation, the submitted representation, changed fields, and a fresh ETag. The UI requires explicit reconciliation and resubmission.

**Rationale**: Last-write-wins could silently overwrite consent, visibility, status, notes, or security configuration. Pessimistic browser locks are fragile and harm recovery.

## Decision 10: Infrastructure, delivery, and observability

**Decision**: Manage AWS resources with Terraform, build reproducible OCI images, and promote the same signed image through environments. Instrument Django and workers with OpenTelemetry into CloudWatch Application Signals, metrics, logs, traces, SLO dashboards, and alarms. Logs use request/actor/tenant correlation identifiers but no candidate content. Enable CloudTrail, GuardDuty, Security Hub, AWS Config, Inspector, and Macie in production accounts.

**Rationale**: The system needs repeatable regional recovery and auditable security configuration, not manual console state. Managed AWS telemetry minimizes operational components.

## Decision 11: Candidate rights workflow

**Decision**: Provide a verified self-service rights center. Access/correction and consent withdrawal/profile hiding take effect immediately. Generate a complete portable export within 24 hours and expire its authenticated encrypted link after 24 hours. Deletion requires step-up verification, consequence preview, and explicit confirmation; hide immediately and erase within 30 days except for precisely scoped active-process/legal-hold data. Expose `PENDING`, `IN_PROGRESS`, `HELD`, `COMPLETED`, `FAILED`, and `CANCELLED` state with support escalation.

**Rationale**: Candidate control must be an operable product workflow, not only a back-office data model. Immediate hiding reduces ongoing disclosure while bounded asynchronous erasure can safely cover primary, derived, cached, exported, workflow, and backup-restoration surfaces.

**Alternatives rejected**:

- **Support-ticket-only rights**: creates avoidable friction and makes routine correction/withdrawal dependent on staff.
- **Immediate irreversible deletion without verification**: increases account-takeover and mistaken-deletion harm.

## Decision 12: Visibility policies

**Decision**: Implement four separate modes: `APPROVED_RECRUITERS`, `MATCHING_ROLES`, `APPLIED_ROLES_ONLY`, and `NOT_LOOKING`. `APPROVED_RECRUITERS` requires a non-empty explicit audience. `criteria.context.opening_id` is the sole authoritative opening context. Only an `OPENING` context containing exactly one active `opening_id` may retrieve `MATCHING_ROLES`, after deterministic candidate-controlled role category, location, work-arrangement, and other designated preferences pass. `AD_HOC` contains no `opening_id`, accesses only explicitly authorized `APPROVED_RECRUITERS` profiles, and never bypasses preferences. Saved-search clients and representations contain no independent opening field; any database opening index is derived, read-only, and constrained to the authoritative context. AI may rank an already eligible set but cannot establish visibility. Applied-role-only access requires the submitted application and current hiring-team authorization.

**Rationale**: Matching-role sourcing and application-only processing are different consent purposes. Separate modes make their audiences explainable and testable.

**Alternatives rejected**:

- **Treat matching as applied-only**: removes the intended consented sourcing workflow.
- **Let semantic similarity establish eligibility**: makes a probabilistic score an authorization decision.

## Decision 13: Candidate-facing status contract

**Decision**: `CandidateFacingStatus` contains only `APPLIED`, `PROFILE_VIEWED`, `SHORTLISTED`, `RECRUITER_INTERESTED`, `INTERVIEW_REQUESTED`, `OFFER_MADE`, `NOT_SELECTED`, and `WITHDRAWN`. Status preview accepts `InternalRecruitingStatus` and maps it to a nullable candidate-facing suggestion. Candidate submission publishes `APPLIED`; candidate-confirmed withdrawal publishes `WITHDRAWN`. First view, Shortlisted, Contacted/Screening, Interviewing, Offered, and Rejected may create the corresponding suggestion, but recruiter publication accepts only an explicitly selected valid `CandidateFacingStatus` and requires preview plus confirmation. Sourced, Not relevant, Hired, and other internal states return a null suggestion and cannot be published without that valid explicit selection.

**Rationale**: One small plain-language vocabulary prevents API/UI/notification drift and avoids implying an unapproved offer or outcome.

## Decision 14: Sourced-candidate work context

**Decision**: Create or reuse exactly one tenant-scoped candidate-work record per candidate and originating search when an authorized recruiter first views, notes, shortlists, or changes internal status; an opening is optional. The record owns contextual notes, internal status, shortlist state, reasons, versions, and audit history. A later application links to it but neither aggregate copies or overwrites the other.

**Rationale**: This supports ad-hoc sourcing without inventing an application and preserves purpose/context boundaries.

**Alternatives rejected**:

- **Auto-create a sourced application**: falsely represents candidate action and corrupts application metrics/consent semantics.
- **Tenant-global candidate notes/status**: loses recruiting purpose and risks cross-opening leakage.

## Decision 15: Tenant and business-unit governance

**Decision**: One tenant is one contracted customer company or legally separate recruiting boundary. Only audited platform onboarding can provision or alter tenant lifecycle/boundaries. Recruiters create business units and openings inside an active tenant. Business units organize work but do not change isolation.

**Rationale**: The tenant identifier remains a stable contractual/security boundary rather than user-created application data.

## Decision 16: Generic informational findings and deterministic short-tenure evaluation

**Decision**: Add a generic, versioned `CandidateFinding` evaluation structure rather than a
feature-specific table. Candidate-controlled employment records retain confirmed or ambiguous date
state, employment type, provenance, confidence, and source spans. Versioned deterministic backend
code evaluates only confirmed completed records and creates one informational `SHORT_TENURE` result
per qualifying non-temporary record when `end_date < start_date + 12 calendar months`. Current roles,
temporary engagements, and insufficient dates produce no recruiter warning. Candidate corrections
recalculate by source-record ID and retire obsolete results. Recruiter projections attach currently
authorized findings only after eligibility, score, and rank have been finalized.

**Rationale**:

- The existing `profile_evidence` structure represents candidate-approved facts used by retrieval;
  reusing it for a warning could accidentally couple the signal to ranking.
- A generic finding structure supports evidence, versioning, recalculation, privacy lifecycle, and
  future informational rules without introducing a `short_tenure` table.
- Separating extraction, deterministic evaluation, and presentation prevents model confidence or
  generated prose from becoming a hiring decision.

**Alternatives rejected**:

- **Reuse `profile_evidence`**: risks treating an informational finding as a match or ranking fact.
- **Create a short-tenure-specific table**: unnecessary schema coupling for one deterministic rule.
- **Ask an LLM whether a candidate is a job hopper**: subjective, consequential, and likely to infer
  missing dates or reasons for departure.
- **Compute findings in the browser**: would make authorization, versioning, correction, audit, and
  cross-tenant behavior inconsistent.

## Resolved Defaults

| Area | Default |
|---|---|
| Supported browsers | Current and previous major versions of Chrome, Edge, Firefox, and Safari; responsive web only |
| Resume upload | PDF/DOC/DOCX, 10 MiB, signature and MIME validation |
| API style | Same-origin JSON REST under `/api/v1`; OpenAPI 3.1; secure cookie session and CSRF |
| Pagination | Cursor pagination; default 25 candidates, maximum 100 |
| Time | Store UTC, render IST initially; IANA time zones for user-visible schedules |
| Locale | English (`en-IN`) at launch; content remains localization-ready |
| Money | Integer minor units plus ISO 4217 currency, default INR |
| IDs | UUIDv7 externally; database-generated internal keys where justified |
| Soft deletion | Only for recoverable workflow objects; privacy deletion erases/anonymizes rather than hiding rows indefinitely |
| AI retention | No prompt bodies in production telemetry; ephemeral request processing only; derived suggestions follow source-record retention |

## Remaining Preconditions, Not Design Unknowns

1. Legal/privacy approval of the production notice, consent text, rights workflow, retention/legal-hold policy, and subprocessor list for India.
2. Production AWS organization/accounts, domains, certificates, DNS, sender identities, KMS ownership, audited platform-onboarding operators, and designated peer security approvers.
3. Selection and approval of a WhatsApp Business provider and templates, or explicit deferral of WhatsApp at launch.
4. Production-shaped evaluation proving the selected in-region Bedrock model meets extraction/search quality, fairness, latency, and cost gates; model availability and lifecycle must be rechecked at implementation and release.
5. Pilot tenant SSO metadata, branding, recruiter data ownership, and support/escalation contacts.
