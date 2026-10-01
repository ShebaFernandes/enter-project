# Planning Quickstart and Verification Guide

This document is the implementation handoff for the technical plan. It defines the intended local topology, configuration contract, and release evidence. It does not implement the application.

## Prerequisites

- Python 3.13 and an isolated virtual environment
- Node.js 22 LTS for TypeScript/Vite build tooling only
- PostgreSQL 16 with `pgvector` and `pg_trgm`
- Docker-compatible runtime for PostgreSQL, Valkey, and local service emulators
- Terraform version pinned by the repository toolchain
- AWS development account with only synthetic data; no developer machine receives production candidate data

## Intended Local Services

```text
web       Django templates + /api/v1
worker    same Python package, SQS/outbox consumers
scheduler local trigger for lifecycle/reconciliation jobs
postgres  transactional data, RLS, full-text, pgvector
valkey    ephemeral cache and abuse counters
s3-local  quarantine/clean/export buckets for synthetic files
mail      captured synthetic email
```

GuardDuty malware scanning, Cognito federation, Bedrock inference, KMS, WAF, and multi-region recovery are verified in AWS integration environments, not simulated as proof of production behavior.

## Configuration Contract

Configuration is environment-driven and validated at startup. Secrets come from AWS Secrets Manager in deployed environments and from ignored local secret files during development.

Required configuration groups:

- `APP_ENV`, canonical origin, secure-cookie and CSRF origins
- PostgreSQL writer/reader endpoints and RLS enforcement mode
- Cognito issuer/client/callback values and workforce federation configuration
- S3 quarantine/clean/export buckets and KMS key ARNs
- SQS queue/DLQ URLs and EventBridge schedule identifiers
- SES identities and optional approved WhatsApp adapter
- Bedrock region/model allowlist and embeddings model/version
- OpenTelemetry destination, sampling, and log-redaction policy
- retention policy version and legal-hold approver group

Production startup fails closed if encryption keys, trusted origins, identity issuer, database TLS, RLS enforcement, audit sink, or clean-bucket policy cannot be verified. Optional AI and notification providers may start unavailable only when the manual/pending experience is enabled and observable.

## Planned Developer Commands

The implementation should provide these stable wrappers rather than requiring contributors to remember service-specific commands:

```bash
make bootstrap       # install pinned dependencies and local hooks
make services        # start synthetic local dependencies
make migrate         # apply schema and RLS migrations
make fixtures        # load generated synthetic tenants/candidates only
make dev             # run web, worker, and asset watcher
make check           # format, lint, type-check, schema checks
make test            # unit and service integration suites
make test-contract   # OpenAPI and event compatibility tests
make test-browser    # Playwright workflow/accessibility/regression tests
make test-security   # dependency, secret, SAST, DAST, IaC, and container checks
make test-load       # production-shaped k6/Locust scenarios
make test-ai         # versioned AI quality/safety/fairness evaluation suite
```

Exact tools may be wrapped differently, but CI and local development must execute the same checks.

## Synthetic Fixture Requirements

Fixtures must be generated, visibly marked synthetic, and cover:

- all five roles, platform-provisioned company tenants, business units, overlapping names, and multi-tenant memberships;
- candidates with `APPROVED_RECRUITERS`, `MATCHING_ROLES`, `APPLIED_ROLES_ONLY`, and `NOT_LOOKING`, including non-empty approved audiences, deterministic preferences, `AD_HOC` contexts without `opening_id`, `OPENING` contexts with exactly one active `criteria.context.opening_id`, saved searches without a top-level opening field, and purpose-specific consent combinations;
- one profile applying to multiple roles with independent answers/status/history;
- applications using only the eight-value `CandidateFacingStatus`, with preview requests accepting `InternalRecruitingStatus`, null suggestions for unmapped internal states, and publication requiring an explicitly selected valid candidate-facing value; notifications with internal `QUEUED`/`SENDING` projected to candidate-facing `PENDING`;
- searches with stable criteria-group and criterion IDs, `ANY`/`ALL` operators, valid group references, and negative fixtures for duplicates or missing groups;
- versioned active-process retention exceptions with exact candidate/application, policy, basis, scope, lifecycle, date, approver, and audit fields;
- sourced candidates with distinct tenant/search candidate-work records, optional openings, contextual notes/status/shortlists, and later linked applications that remain independent;
- Indian locations, names, currencies, time zones, long text, and translated-length content;
- clean, malformed, oversized, password-protected, macro-bearing, and malware-test resumes;
- ambiguous and adversarial search/resume text, including prompt-injection attempts;
- pending, retrying, sent, failed, expired, withdrawn, legal-hold, and deletion states;
- access/correction/withdraw/hide/export/delete rights requests in pending, in-progress, held, completed, failed, cancelled, expired-download, disputed, and support-escalated states;
- stale versions for consent, visibility, note, status, and administration conflict tests.

No fixture may be copied or transformed from a real candidate.

## Verification Matrix

| Gate | Minimum evidence |
|---|---|
| Functional | Unit/service tests plus Playwright for every critical mockup journey and state |
| Existing design | Approved baseline screenshots and interaction inventory; intentional deltas documented |
| Accessibility | axe with no serious/critical issues plus retained post-implementation manual evidence for keyboard-only completion, focus/error/live-region behavior, representative screen readers, high contrast, reduced motion, touch/pointer input, 200% zoom, and 320px through desktop layouts |
| Responsive | 320, 375, 768, 1024, and 1440 CSS-pixel views; long content; touch and pointer |
| Authorization | Deny-by-default matrix tests for every role/operation; object and tenant negative tests; direct API tests |
| Tenant isolation | Generated cross-tenant property tests plus RLS tests with unset/wrong context |
| Privacy | Consent/visibility propagation, export/delete, cache/index/checkpoint erasure, backup restoration plus deletion/withdrawal/revocation event replay |
| Candidate rights | Immediate access/correction/withdraw/hide; export ready <=24h and link expiry 24h; step-up deletion, immediate hiding, <=30-day erasure, exact holds, visible states, support escalation |
| Concurrency | Stale writes return authorized current and attempted data, never silently overwrite |
| Files | Upload type/size/signature checks, clean-tag policy, scan failure, parser sandbox, no pre-scan download |
| Abuse | Every specified identity/network threshold, generic response, retry time, override audit, no permanent auto-lockout |
| AI/RAG | Schema validity, strict-filter correctness, provenance/citations, authorization-before-retrieval, injection resistance, protected-trait/proxy leakage, fairness, privacy/residency, lifecycle, latency, cost, and deterministic/manual fallback promotion thresholds |
| Visibility | Deterministic active-opening eligibility for matching roles before AI; submitted-application/team gate for applied-only; approved audience and not-looking denial |
| Availability | Multi-AZ fault injection and core-path SLO dashboards |
| Recovery | Quarterly isolated restore proves <=15-minute RPO and <=4-hour RTO, auth/RLS/audit integrity, and deletion replay |
| Scale | 100 tenants, 1M candidate profiles, 1,000 active users; normal search <=3-second p95 |
| Security | Threat model, ASVS-oriented review, SAST/SCA/secrets/IaC/container/DAST, independent penetration test closure |
| Administrative governance | Redacted audit-history access is itself logged; periodic membership, privileged-role, purpose-grant, emergency-grant, and audit-access reviews produce decisions and revocation evidence |
| Incident response | Candidate-data incident runbook covers triage, containment, preservation, India notification decision/approval, tenant/candidate communications, recovery, and post-incident regression; tabletop exercise closes findings |
| Usability | Moderated protocols verify SC-001/002/003/005/007/008/012 thresholds; instrumented browser tests verify feedback starts within one second for SC-013 |

## Release Promotion

1. **Local/CI**: synthetic data; deterministic suites and contract checks.
2. **Development AWS**: managed identity, S3 scan path, Bedrock model gateway, queues, and observability with synthetic data.
3. **Staging**: production topology and production-shaped synthetic load; restore and failover rehearsals.
4. **Internal alpha**: trained internal users; no real candidate data.
5. **Pilot**: two to five approved tenants, consented records, feature flags, enhanced support/on-call, and daily privacy/error review.
6. **General launch**: progressive tenant enablement after legal/privacy/security/accessibility/DR/performance gates pass.

Rollback uses the previously signed application image and backward-compatible expand/contract database migrations. Privacy and security fixes may disable a feature through a server-side flag; rollback must never resurrect deleted data, undo consent withdrawal, or republish hidden profiles.

## Definition of Production Ready

- All specification acceptance criteria and constitution gates have traceable passing evidence.
- No unresolved high-severity security, privacy, accessibility, data-loss, or critical-workflow defect exists.
- Operations owns dashboards, alerts, on-call, incident response, DLQ/reconciliation, restore, failover, key rotation, and emergency-access runbooks.
- Legal/privacy has approved notices, consent, rights, retention, legal hold, subprocessors, and communications.
- Model/version evaluation has passed and in-region availability is verified immediately before release.
- Pilot rollback and tenant offboarding have been rehearsed.
## Approved frontend migration verification

Follow [frontend-migration.md](./frontend-migration.md) and the FM tasks before Phase 10. This is a future execution guide, not evidence that checks have run. First record git status, checkpoint 66a3acd and parent 5372072, mockup SHA-256, test collection and repository-wide mypy scope. Inventory any subsequent changes. Establish and test legacy renderers before WIP reuse. Use existing LOCAL_RECRUITER_BOOTSTRAP_URL, LOCAL_CANDIDATE_BOOTSTRAP_URL and configured Tenant Admin/application recruiter browser bootstrap helpers; do not invent an auth bypass.

Use server-controlled per-route legacy/React selection. Test both modes with identical real API-backed synthetic test fixtures, current session/CSRF, and negative tenant/role/field-scope cases. New / and /jobs/ paths first receive Django fallback. Do not store protected workflow state in browser storage. Capture immutable reference and implementation screenshots at 1440×1000, 1024×768, 390×844, 320×844 and 200% zoom. Freeze test clocks/animation only in test harnesses; never edit mockup source. Record each visual difference with state, reason and approval. Fonts use local assets or measured documented fallback; temporary text wordmark difference is explicit.

Run focused functional/security/browser/accessibility/build checks before each slice cutover; retain screenshot and rollback evidence. FM14 runs complete PostgreSQL collection/suite, mypy . with unchanged scope, Ruff format/lint, Django checks and migration drift check, TypeScript/ESLint/Prettier, Vite production build and complete Playwright/accessibility suite once. Compare test inventory against baseline and original mockup hash. Disable the affected route flag to roll back; retain data, contracts and URLs, never replay a mutation to change renderer. Phase 10 and production deployment remain deferred.
