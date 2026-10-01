# Tasks: Integrated Recruiter and Candidate Workflows

**Input**: Design documents from `specs/001-recruiter-candidate-workflows/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, and `.specify/memory/constitution.md`

**Tests**: Required. Within each user-story phase, write the listed tests first and confirm that they fail for the intended missing behavior before implementation.

**Organization**: Tasks are dependency ordered and grouped by user story. The shared tenant/business-unit/opening shell is foundational because Matching roles and applications depend on active openings. US6 precedes US4 so applicant linking exists before the combined sourced/applicant management tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: May run in parallel after phase prerequisites are satisfied because it targets different files and has no dependency on incomplete work.
- **[Story]**: Maps the task to a specification user story.
- Every checklist item names an exact target path.

---

## Phase 1: Setup and Mockup Baseline

**Purpose**: Establish reproducible tooling and freeze the existing HTML/CSS/JavaScript experience as a read-only preservation baseline.

- [X] T001 Inventory screens, entry points, controls, states, storage keys, handoffs, speech behavior, and responsive behavior in the unmodified mockup in `docs/baseline/mockup-inventory.md`
- [X] T002 [P] Capture synthetic-data screenshots at 320, 375, 768, 1024, and 1440 CSS pixels and 200% zoom in `app/tests/browser/baselines/README.md`
- [X] T003 [P] Record keyboard order, focus behavior, labels, live regions, validation, dialogs, and known accessibility gaps in `docs/baseline/accessibility-inventory.md`
- [X] T004 Create the Django modular-monolith and consolidated frontend skeleton defined by the plan in `app/manage.py`, `app/config/`, `app/modules/`, and `app/frontend/`
- [X] T005 Pin Python runtime, test, lint, type-check, SBOM, and dependency-audit tooling in `app/pyproject.toml`
- [X] T006 [P] Configure TypeScript, Vite, ESLint, formatting, axe, and Playwright without a UI framework in `app/package.json`, `app/tsconfig.json`, `app/vite.config.ts`, and `app/playwright.config.ts`
- [X] T007 [P] Add non-root, pinned, reproducible web and worker images in `app/Dockerfile` and `app/docker/entrypoint.sh`
- [X] T008 Add local PostgreSQL/pgvector, Valkey, S3-compatible storage, and captured-mail services using synthetic data in `compose.yaml`
- [X] T009 Add stable bootstrap, migration, fixture, check, contract, browser, security, DAST, load-test, and AI-evaluation commands in `Makefile`
- [X] T010 [P] Define validated configuration and a secret-free example for local, test, and production environments in `app/config/environment.py` and `.env.example`
- [X] T011 [P] Create synthetic factories for all roles, tenants, visibility modes, workflow states, long content, failures, stale versions, and recruiter-entered synthetic candidates in `app/tests/factories/`
- [X] T012 Configure lint/type/schema, unit/database/contract, browser/accessibility, SAST/DAST, container/IaC, and evidence-retention CI stages in `.github/workflows/ci.yml`
- [X] T013 Document module ownership, permitted dependencies, and the ban on direct cross-module model mutation in `docs/architecture-decisions/0001-modular-monolith.md`
- [X] T014 Record supported current/previous Chrome, Edge, Firefox, and Safari versions and the representative manual/automated test matrix in `docs/quality/browser-support.md`

**Checkpoint**: The repository is reproducible and the original mockup has a reviewable visual, behavioral, responsive, speech, and accessibility baseline.

---

## Phase 2: Foundational Security, Shared Data, and Opening Prerequisites

**Purpose**: Deliver the shared security controls and the tenant/opening shell required by search and applications.

**Critical**: No story implementation begins until authorization, isolation, audit, safe-storage, and opening-prerequisite tests pass.

- [X] T015 Configure secure cookies, CSRF/trusted origins, CSP, HTTPS/HSTS, upload limits, redacted logging, and India-region allowlists in `app/config/settings/base.py`, `app/config/settings/local.py`, and `app/config/settings/production.py`
- [X] T016 [P] Implement correlation IDs, RFC 9457 problem responses, safe exception mapping, and progress-event primitives in `app/modules/operations/middleware.py` and `app/modules/operations/problems.py`
- [X] T017 [P] Implement strong ETags and `If-Match` conflicts containing authorized stored state, attempted changes, changed fields, and a fresh ETag in `app/modules/operations/concurrency.py`
- [X] T018 [P] Implement idempotency-key persistence and response replay for create and consequential operations in `app/modules/operations/idempotency.py`
- [X] T019 Create identity records with immutable Cognito subject, verified-email lookup HMAC, encrypted email, lifecycle status, and authentication timestamps in `app/modules/identity/models.py`
- [X] T020 Create tenant, business-unit, membership, opening, and hiring-team model shells with the exact states and constraints in `app/modules/tenancy/models.py` and `app/modules/recruiting/models.py`
- [X] T021 Create the application shell with unique `(opening_id, candidate_profile_id)`, independent version/history references, `CandidateFacingStatus=APPLIED|PROFILE_VIEWED|SHORTLISTED|RECRUITER_INTERESTED|INTERVIEW_REQUESTED|OFFER_MADE|NOT_SELECTED|WITHDRAWN`, and nullable `suggested_candidate_status` in `app/modules/recruiting/models.py`
- [X] T022 Create the recruiter-entered candidate shell with mandatory `source_type=RECRUITER_ENTERED_SYNTHETIC`, visible source label, tenant ownership, no contact/resume fields, and no candidate-profile merge path in `app/modules/recruiting/models.py`
- [X] T023 Generate reviewed constraints and indexes for T019–T022 in `app/modules/identity/migrations/`, `app/modules/tenancy/migrations/`, and `app/modules/recruiting/migrations/`
- [X] T024 Implement candidate and Platform Security Admin assignments separately from tenant membership and select exactly one server-validated tenant context per request in `app/modules/tenancy/context.py`
- [X] T025 Implement Cognito OIDC/PKCE callbacks, candidate email verification, workforce federation, MFA assurance, rotating `__Host-` sessions, revocation, and global sign-out in `app/modules/identity/services.py` and `app/modules/identity/views.py`
- [X] T026 Implement deny-by-default role, purpose, tenant, object, field, consent, and grant authorization from the matrix in `app/modules/tenancy/policy.py`
- [X] T027 Implement transaction-local RLS context derived only from authenticated server state and fail closed when missing or invalid in `app/modules/tenancy/rls.py` and `app/modules/tenancy/migrations/0002_rls.py`
- [X] T028 Implement platform-only tenant provisioning plus tenant merge/split/suspend/reactivate/close authorization boundaries in `app/modules/tenancy/provisioning.py` and `app/modules/tenancy/platform_views.py`
- [X] T029 Implement business-unit lifecycle and opening create/read/update/pause/close services needed by downstream stories in `app/modules/tenancy/business_units.py` and `app/modules/recruiting/openings.py`
- [X] T030 Implement business-unit, opening, and platform tenant-provisioning endpoints from the OpenAPI contract in `app/modules/tenancy/views.py` and `app/modules/recruiting/opening_views.py`
- [X] T031 Implement tenant-scoped recruiter-entered synthetic candidate creation/listing with immutable provenance and environment enforcement in `app/modules/recruiting/recruiter_entered.py` and `app/modules/recruiting/opening_views.py`
- [X] T032 Create purpose-specific access grants and break-glass requests with a required non-empty `field_scope`, exact read scope, different-admin approval, one-hour maximum, revocation, and immediate Tenant Admin notification in `app/modules/tenancy/grants.py`
- [X] T033 Implement immutable, value-minimized, hash-chained audit events that exclude resumes, note bodies, tokens, contacts, and notification bodies in `app/modules/audit/models.py` and `app/modules/audit/service.py`
- [X] T034 [P] Implement daily KMS-signed audit checkpoints to S3 Object Lock and fail privileged actions if durable auditing fails in `app/modules/audit/checkpoints.py`
- [X] T035 [P] Implement versioned encryption and blind-index/HMAC helpers with plaintext-log protections in `app/modules/operations/crypto.py`
- [X] T036 Implement the transactional outbox, minimized event envelopes, processed-event idempotency, relay, and reconciliation in `app/modules/operations/outbox.py` and `app/modules/operations/workers.py`
- [X] T037 Create notification records with encrypted destination, consent basis, internal `QUEUED|SENDING|SENT|FAILED|CANCELLED` state, candidate-safe `PENDING|SENT|FAILED|CANCELLED` projection mapping, unique idempotency key, at most five attempts over 24 hours, and safe terminal errors in `app/modules/communications/models.py`
- [X] T038 Implement SES and disabled-until-approved WhatsApp adapters with signed callbacks, bounded retry, DLQ redrive, and duplicate suppression in `app/modules/communications/adapters.py` and `app/modules/communications/workers.py`
- [X] T039 [P] Define SQS queues/DLQs, EventBridge schedules, KMS keys, Secrets Manager entries, and queue alarms in `infra/modules/async/main.tf`
- [X] T040 Implement verified-identity-plus-network rate limits for sign-in, OTP, uploads, applications, searches, and exports in `app/modules/abuse/service.py`
- [X] T041 Implement escalating temporary delays, `Retry-After`, anomaly tightening, step-up challenge, audited overrides, and no permanent automatic lockout in `app/modules/abuse/policy.py` and `app/modules/abuse/views.py`
- [X] T042 [P] Add contract tests for sessions, RFC 9457 errors, ETags, idempotency, rate-limit headers, and non-enumerating responses in `app/tests/contract/test_foundation_contracts.py`
- [X] T043 [P] Add exhaustive five-role operation-matrix, guessed-ID, revoked-session, stale-link, and tenant-switch tests in `app/tests/security/test_authorization_matrix.py`
- [X] T044 [P] Add RLS tests for missing/wrong/correct tenant contexts, cross-tenant joins, and object/field grants in `app/tests/database/test_rls_isolation.py`
- [X] T045 [P] Add break-glass tests for missing/empty `field_scope`, self-approval denial, independent approval, narrow scope, notification, expiry, revocation, service-layer revalidation, and audit completeness in `app/tests/security/test_emergency_access.py`
- [X] T046 [P] Add audit tests for minimization, hash-chain verification, durable checkpoints, denied access, overrides, admin actions, and DLQ redrive in `app/tests/security/test_audit_controls.py`
- [X] T047 [P] Add rate-limit tests for every identity/network threshold, escalation, anomaly tightening, override, and recovery path in `app/tests/security/test_abuse_controls.py`
- [X] T048 [P] Add notification tests for idempotency, callback validation, five-attempt/24-hour bounds, DLQ behavior, internal delivery states, `QUEUED`/`SENDING` to candidate-facing `PENDING` mapping, and non-exposure of internal states in `app/tests/integration/test_notification_delivery.py`
- [X] T049 [P] Add tenant-governance/opening prerequisite tests for platform-only provisioning, unit isolation, hiring-team scope, and recruiter-entered synthetic provenance in `app/tests/security/test_tenant_opening_foundation.py`
- [X] T050 Add request/response/error, examples, conditional-schema, `InternalRecruitingStatus` preview, `CandidateFacingStatus` publication, saved-search no-top-level-opening, notification-projection, and local-reference validation against all paths in `specs/001-recruiter-candidate-workflows/contracts/openapi.yaml` in `app/tests/contract/test_openapi_conformance.py`
- [X] T051 Add event-schema compatibility and data-minimization validation against `specs/001-recruiter-candidate-workflows/contracts/events.md` in `app/tests/contract/test_event_contracts.py`

**Checkpoint**: Shared security controls and the platform-provisioned tenant/business-unit/opening foundation are ready before search or applications.

---

## Phase 3: User Story 1 — Candidate Creates and Controls a Profile (Priority: P1) — Recommended MVP

**Goal**: A verified candidate can create a truthful profile, control visibility and consent, and exercise all privacy rights.

**Independent Test**: Create and publish a synthetic candidate profile, exercise all four visibility modes, and complete every rights-center path with the specified verification, timing, hold, status, and accessibility behavior.

### Tests for User Story 1

- [X] T052 [P] [US1] Add validation tests for required fields, fractional nonnegative experience, currency/period compensation, availability-date consistency, safe HTTP(S) links, optional fields, and the 300-character narrative in `app/tests/unit/candidate/test_profile_validation.py`
- [X] T053 [P] [US1] Add resume tests for type/size, quarantine, malware scan, parse states, provenance, hallucination prevention, manual fallback, and no pre-scan disclosure in `app/tests/integration/candidate/test_resume_pipeline.py`
- [X] T054 [P] [US1] Add visibility tests for non-empty `APPROVED_RECRUITERS` audiences, non-empty `MATCHING_ROLES` preferences, Applied roles only, Not looking, withdrawal, immediate hiding, schema validation, and service-layer revalidation in `app/tests/security/test_candidate_visibility.py`
- [X] T055 [P] [US1] Add API tests for immediate verified access/correction/withdrawal/hiding and request-state/support-escalation behavior in `app/tests/contract/test_candidate_rights_api.py`
- [X] T056 [P] [US1] Add export tests for full scope, 24-hour completion, authenticated delivery, 24-hour expiry, rate limiting, and auditing in `app/tests/integration/candidate/test_rights_export.py`
- [X] T057 [P] [US1] Add deletion tests for absent/stale/recent step-up, required consequence confirmation, immediate hiding, 30-day completion, exact versioned `ActiveProcessRetentionException` fields/lifecycle, terminating-event resolution, legal holds, irreversible analytics, and service-layer revalidation in `app/tests/integration/candidate/test_rights_deletion.py`
- [X] T058 [P] [US1] Add browser tests for profile editing, consent, conflicts, rights status, exports, deletion, support escalation, keyboard use, and responsive reflow in `app/tests/browser/candidate/rights-center.spec.ts`
- [X] T200 [P] [US1] Add employment-history validation and correction tests covering stable record IDs, complete/partial/ambiguous dates, current-role end-date rules, employment-type enums, extraction confidence/source spans, and prohibition on invented dates, duration, employer, type, or departure reason in `app/tests/unit/candidate/test_employment_history.py`

### Implementation for User Story 1

- [X] T059 [P] [US1] Create profile, skill, contact, link, visibility, consent, resume, extracted-fact, and evidence models with the exact constraints in `app/modules/candidate/models.py`
- [X] T201 [P] [US1] Add candidate-controlled `EmploymentRecord` with nullable date values, `CONFIRMED|SUGGESTED|AMBIGUOUS|MISSING` field states, current/completed consistency, `PERMANENT|INTERNSHIP|APPRENTICESHIP|FIXED_TERM_CONTRACT|CONSULTING|SEASONAL|OTHER_TEMPORARY|OTHER|UNKNOWN` type, provenance, confidence/source spans, versioning, and no departure-reason field in `app/modules/candidate/models.py`
- [X] T060 [P] [US1] Create rights request, rights export, legal hold, deletion ledger, and versioned `ActiveProcessRetentionException` with candidate/application reference, policy version, legal basis, retained scope, lifecycle state, start/review/resolution dates, terminating event, approver, and audit references in `app/modules/privacy/models.py`
- [X] T061 [US1] Generate profile/privacy migrations with one profile per verified identity, publication constraints, and rights indexes in `app/modules/candidate/migrations/` and `app/modules/privacy/migrations/`
- [X] T062 [US1] Implement profile and employment-history access, correction, completeness, truthful-field validation, publication, optimistic reconciliation, and minimized `profile.employment_history_changed.v1` emission by changed record ID/version in `app/modules/candidate/services.py`
- [X] T063 [US1] Implement four-mode visibility and consent policy with non-empty explicit audience for `APPROVED_RECRUITERS`, deterministic preferences for `MATCHING_ROLES`, immediate withdrawal/hiding, conditional validation, and no discoverability before valid consent in `app/modules/candidate/visibility.py`
- [X] T064 [US1] Implement quarantined upload, MIME/signature/size checks, malware scan gate, parsing, provenance, partial/failure states, manual fallback, and nullable employment-date/type suggestions with confidence/source spans that never invent missing values or departure reasons in `app/modules/candidate/resume_service.py`
- [X] T065 [US1] Implement rights access/correction/withdrawal/hiding orchestration, visible states, expected completion, failure reason, and escalation in `app/modules/privacy/services.py`
- [X] T066 [US1] Implement minimized export generation, authenticated download, 24-hour SLA/expiry, cleanup, and audit in `app/modules/privacy/export_service.py` and `app/modules/privacy/workers.py`
- [X] T067 [US1] Implement recent subject-bound step-up plus explicit consequence confirmation, immediate hiding, versioned `ActiveProcessRetentionException` creation/review/resolution, 30-day erasure, anonymized aggregates, and deletion evidence in `app/modules/privacy/deletion_service.py`
- [X] T068 [US1] Implement profile, employment-history, visibility, resume, and rights endpoints from the OpenAPI contract in `app/modules/candidate/views.py`, `app/modules/privacy/views.py`, and `app/config/urls.py`
- [X] T069 [P] [US1] Build the accessible profile and employment-history editor, evidence review, date/type ambiguity correction, completion summary, consent, and visibility controls in `app/frontend/candidate/profile.ts` and `app/frontend/styles/candidate-profile.css`
- [X] T070 [P] [US1] Build resume idle/reading/success/partial/failure UI with manual-entry recovery in `app/frontend/candidate/resume.ts` and `app/frontend/templates/candidate/profile.html`
- [X] T071 [US1] Build the verified rights center with request history, export expiry, deletion confirmation, holds, failures, and escalation in `app/frontend/candidate/rights-center.ts` and `app/frontend/templates/candidate/rights-center.html`
- [X] T072 [US1] Add 320px-through-desktop reflow, 200% zoom, focus, error summaries, live regions, and reduced motion in `app/frontend/styles/forms.css` and `app/frontend/styles/responsive.css`
- [X] T073 [US1] Add consent-renewal scheduling 30 days before 12-month inactivity expiry, active-process exception review/terminating-event handling, and expiry deletion/anonymization in `app/modules/privacy/retention.py` and `app/modules/privacy/workers.py`
- [X] T074 [US1] Add candidate lifecycle and rights audit emission without sensitive values in `app/modules/privacy/audit.py`
- [X] T075 [US1] Run and record failing-then-passing US1 evidence in `docs/evidence/us1-candidate-profile-and-rights.md`

**Checkpoint**: US1 is independently deployable with synthetic data as the recommended MVP.

---

## Phase 4: User Story 2 — Recruiter Searches for Candidates (Priority: P1)

**Goal**: An authorized recruiter can sign in and execute explainable deterministic searches with typed or optional speech input.

**Independent Test**: Sign in through the recruiter entry point, test typed and speech states, then search a fixed corpus and prove every result satisfies strict criteria and applicable visibility grants.

### Tests for User Story 2

- [x] T076 [P] [US2] Add recruiter identity tests for verified work email, personal/invalid/unverified rejection, non-enumeration, sign-out, saved-route denial, and navigation-history protection in `app/tests/browser/recruiter/authentication.spec.ts`
- [x] T077 [P] [US2] Add search contract tests proving `criteria.context` is authoritative, `AD_HOC` rejects any `opening_id` property, `OPENING` requires exactly one active `opening_id`, no independent opening field is accepted/exposed, and grouped criteria, pagination, status filters, recent searches, evidence, examples, and declared errors conform in `app/tests/contract/test_search_api.py`
- [x] T078 [P] [US2] Add deterministic eligibility tests proving only valid active-opening `OPENING` searches retrieve `MATCHING_ROLES`, `AD_HOC` retrieves only explicitly authorized `APPROVED_RECRUITERS`, preferences are never bypassed, Applied roles only/Not looking remain excluded, and AI cannot establish eligibility in `app/tests/security/test_search_visibility.py`
- [x] T079 [P] [US2] Add ranking tests for requirement/preference/exclusion groups, `ANY|ALL` semantics, duplicate/missing/cross-search group references, stable IDs, unknowns, stable ties, and protected/proxy exclusion in `app/tests/unit/search/test_ranking.py`
- [x] T080 [P] [US2] Add browser tests for side-panel states, empty/loading/error/results/filter/detail states, persistence, keyboard use, and responsive cards in `app/tests/browser/recruiter/search.spec.ts`
- [x] T081 [P] [US2] Add speech tests for unsupported, denied, listening, transcribing, ready, failed, editable transcript, and no-auto-submit states in `app/tests/browser/recruiter/speech-search.spec.ts`
- [x] T202 [P] [US2] Add deterministic `SHORT_TENURE` tests proving an 8-month completed permanent role produces one informational finding, a 12-month role/current 8-month role/missing or ambiguous dates/internship/fixed-term role produce no warning, multiple qualifying roles produce separate findings, correction removes obsolete findings, and findings leave eligibility, score, rank, recommendation, application status, and outcome unchanged in `app/tests/unit/search/test_candidate_findings.py`
- [x] T203 [P] [US2] Add contract, authorization, and presentation tests proving cross-tenant or unauthorized finding access is denied and authorized APIs/UI expose only neutral `SHORT_TENURE` messages plus employment-record ID, company, confirmed dates, calculated duration, calculation version, and evaluation time without a departure reason in `app/tests/contract/test_candidate_findings_api.py` and `app/tests/browser/recruiter/candidate-findings.spec.ts`

### Implementation for User Story 2

- [x] T082 [P] [US2] Create search definition whose authoritative `criteria.context` is `AD_HOC` without `opening_id` or `OPENING` with exactly one `opening_id`, plus optional server-derived read-only opening index, stable criteria-group/criterion entities with `ANY|ALL`, result snapshot, evidence, and recent-search models with seven-day expiry and six-ad-hoc-search cap in `app/modules/search/models.py`
- [x] T204 [P] [US2] Add generic versioned `CandidateFinding` storage with `FOUND|NOT_FOUND|INSUFFICIENT_DATA|EXCLUDED`, source-record identity/version, informational severity, evidence, calculation version/time, supersession, audit references, and unique active source/code/version evaluation in `app/modules/candidate/models.py` and `app/modules/candidate/migrations/`
- [x] T205 [US2] Implement versioned deterministic calendar-month `SHORT_TENURE` evaluation, temporary/current-role exclusions, insufficient-data marking, per-record findings, correction-triggered recalculation/retirement, minimized events, and a structural prohibition on writes to eligibility, score, rank, recommendation, status, or outcome in `app/modules/candidate/finding_evaluators.py` and `app/modules/candidate/finding_events.py`
- [x] T083 [US2] Generate constraints requiring any derived opening foreign key to be null for `AD_HOC` and equal `criteria.context.opening_id` for `OPENING`, plus active-reference support, group/criterion uniqueness and composite references, indexes, tenant uniqueness, and retention migrations in `app/modules/search/migrations/`
- [x] T084 [US2] Implement work-identity eligibility, global navigation/session projection, sign-out, and protected-route history controls in `app/modules/identity/recruiter_access.py` and `app/frontend/shared/navigation.ts`
- [x] T085 [US2] Implement service-layer validation of the sole authoritative `criteria.context` before ranking: exactly one active tenant-owned opening plus preferences for `MATCHING_ROLES`, no `opening_id` property and explicit audience for `AD_HOC`, derived-field equality, and submitted-application team authorization for Applied roles only in `app/modules/search/eligibility.py`
- [x] T086 [US2] Implement requirement/preference/exclusion group evaluation with exact `ANY|ALL` semantics, group-reference validation, explainable scoring, stable ordering, unknown disclosure, and protected-field denial in `app/modules/search/engine.py`
- [x] T087 [US2] Implement tenant-safe context-aware search, pagination, filters, candidate detail projection, authorized post-ranking informational-finding projection, and recent-search endpoints with OpenAPI-aligned conditional validation in `app/modules/search/views.py`
- [x] T088 [US2] Add query indexes, full-text/vector preparation, query timeouts, and safe degradation in `app/modules/search/query.py`
- [x] T089 [P] [US2] Build recruiter entry, signed-in navigation, prompt, side panel, cards, filters, evidence, neutral informational findings, and detail dialog in `app/frontend/recruiter/search.ts` and `app/frontend/templates/recruiter/search.html`
- [x] T206 [US2] Add the OpenAPI `CandidateFinding`/`ShortTenureEvidence` projection and deterministic neutral message presenter after current visibility, purpose, tenant, object, and field-scope authorization in `app/modules/search/projections.py` and `app/frontend/recruiter/candidate-findings.ts`
- [x] T090 [P] [US2] Implement progressive Web Speech integration with typed fallback and all declared states in `app/frontend/recruiter/speech-search.ts`
- [x] T091 [P] [US2] Implement 320px keyboard-safe recruiter search layouts in `app/frontend/styles/recruiter-search.css`
- [x] T092 [US2] Add refresh persistence and unsaved-navigation protection for prompt, criteria, filters, and selection in `app/frontend/shared/persistence.ts`
- [x] T093 [US2] Add search access/result-view audit events and minimized metrics in `app/modules/search/audit.py`
- [x] T094 [US2] Run and record fixed-corpus, visibility, authentication, and speech evidence in `docs/evidence/us2-deterministic-search.md`

**Checkpoint**: US2 returns only authorized, deterministically eligible candidates and preserves typed search when speech is unavailable.

---

## Phase 5: User Story 3 — Recruiter Reviews Search Intent (Priority: P1)

**Goal**: Recruiters inspect, quantify, and correct interpreted criteria before ambiguous searches run.

**Independent Test**: Submit clear and ambiguous prompts, edit every criterion type, and verify estimated impact and final results use exactly the confirmed criteria.

### Tests for User Story 3

- [x] T095 [P] [US3] Add structured-criteria tests for stable group/criterion IDs, required group references, `ANY|ALL`, supported fields, ambiguity, exclusions, protected data, malicious text, and deterministic estimated counts in `app/tests/unit/ai/test_intent_extraction.py`
- [x] T096 [P] [US3] Add contract tests proving ambiguous prompts route to review, every criterion references one submitted group, invalid/duplicate references fail, and recruiter edits override model output without changing stable IDs in `app/tests/contract/test_criteria_review_api.py`
- [x] T097 [P] [US3] Add browser tests for group and criterion add/edit/remove, stable IDs, group membership, `ANY|ALL`, estimated impact, original prompt, keyboard use, errors, and reflow in `app/tests/browser/recruiter/criteria-review.spec.ts`
- [x] T098 [P] [US3] Add golden-set, injection, timeout, invalid-output, and no-model fallback evaluations in `app/tests/ai/test_search_intent_eval.py`

### Implementation for User Story 3

- [x] T099 [US3] Implement versioned intent schemas with stable criteria-group/criterion IDs, `ANY|ALL`, required group references, ambiguity thresholds, validation, and protected-attribute rejection in `app/modules/ai/intent_schema.py`
- [x] T100 [US3] Implement the bounded Bedrock adapter with regional endpoint, timeout, constrained output, and redacted telemetry in `app/modules/ai/bedrock.py`
- [x] T101 [US3] Implement LangGraph only for parse-validate-clarify with minimized checkpoints and deterministic fallback in `app/modules/ai/search_graph.py`
- [x] T102 [US3] Implement deterministic estimated-count and criteria preview/update/execute endpoints that preserve IDs and reject missing/duplicate/cross-search group references in `app/modules/search/criteria_views.py`
- [x] T103 [P] [US3] Build criteria review with original prompt, stable groups and criteria, group membership, `ANY|ALL` controls, exclusions, estimated impact, and confirmation in `app/frontend/recruiter/criteria-review.ts` and `app/frontend/templates/recruiter/criteria-review.html`
- [x] T104 [US3] Configure synthetic/de-identified LangSmith development/staging tracing and production-off default in `app/modules/ai/observability.py`
- [x] T105 [US3] Run and record ambiguity, estimated-impact, and AI-boundary evidence in `docs/evidence/us3-criteria-review.md`

**Checkpoint**: US3 keeps model output advisory and makes every operative criterion and expected impact visible.

---

## Phase 6: User Story 6 — Candidate Applies and Tracks Progress (Priority: P2)

**Goal**: Candidates can review open roles, submit independent applications, and track the canonical eight statuses.

**Independent Test**: Apply to multiple roles with one profile and prove independent answers, consent, timestamps, audit, progress, and notification preferences.

### Tests for User Story 6

- [X] T106 [P] [US6] Add public-opening/application API tests for one profile/multiple applications, unique role application, consent/timestamps, candidate-confirmed `WITHDRAWN`, idempotency, validation, and rate limits in `app/tests/contract/test_application_api.py`
- [X] T107 [P] [US6] Add status tests proving initial `APPLIED`, only the approved eight public values, application-scoped `WITHDRAWN`, nullable unmapped suggestions, per-application isolation, explicit recruiter publication, and no internal leakage in `app/tests/integration/candidate/test_application_status.py`
- [X] T108 [P] [US6] Add browser tests for public role essentials, validation, duplicate submission, eight-status progress, channel preferences, candidate-safe `PENDING|SENT|FAILED|CANCELLED` notification states, keyboard use, and reflow in `app/tests/browser/candidate/application.spec.ts`
- [X] T109 [P] [US6] Add failure tests for closed roles, data/auth outages, notification outage, stale edits, safe retry, refresh persistence, and unsaved warnings in `app/tests/integration/candidate/test_application_failures.py`

### Implementation for User Story 6

- [X] T110 [US6] Extend application storage for answers, consent context, immutable submission time, the approved eight-status enum, nullable `suggested_candidate_status`, channel preferences, and candidate-work link without history overwrite in `app/modules/recruiting/application_models.py`
- [X] T111 [US6] Generate application-answer, consent, preference, and status-history migrations in `app/modules/recruiting/migrations/`
- [X] T112 [US6] Implement public opening read, application submit, and candidate-confirmed application withdrawal with profile reuse, open-state validation, uniqueness, idempotency, initial `APPLIED`, and application-scoped `WITHDRAWN` events in `app/modules/recruiting/applications.py`
- [X] T113 [US6] Implement candidate-owned application listing/status history using exactly `APPLIED|PROFILE_VIEWED|SHORTLISTED|RECRUITER_INTERESTED|INTERVIEW_REQUESTED|OFFER_MADE|NOT_SELECTED|WITHDRAWN` in `app/modules/recruiting/candidate_progress.py`
- [X] T114 [US6] Implement public role, application, candidate-confirmed withdrawal, progress, and per-application notification-preference endpoints from OpenAPI in `app/modules/recruiting/candidate_views.py`
- [X] T115 [US6] Implement consent-aware email/WhatsApp status notifications with internal-to-candidate delivery-state projection, no `SENDING` exposure, and retry-safe links in `app/modules/communications/application_notifications.py`
- [X] T116 [P] [US6] Build accessible public role details and quick application with validation and duplicate-safe submission in `app/frontend/candidate/application.ts` and `app/frontend/templates/candidate/application.html`
- [X] T117 [P] [US6] Build the application list, eight-status timeline, channel preferences, and `PENDING|SENT|FAILED|CANCELLED` delivery display in `app/frontend/candidate/progress.ts` and `app/frontend/templates/candidate/progress.html`
- [X] T118 [US6] Add responsive layouts, one-second feedback, refresh persistence, and unsaved-navigation protection in `app/frontend/styles/candidate-applications.css` and `app/frontend/shared/persistence.ts`
- [X] T119 [US6] Add application, consent, status, and notification audit events without answer/contact values in `app/modules/recruiting/application_audit.py`
- [X] T120 [US6] Run and record multi-role, status-vocabulary, persistence, and failure evidence in `docs/evidence/us6-application-progress.md`

**Checkpoint**: US6 provides independent per-role applications before US4 links and manages applicant records.

---

## Phase 7: User Story 4 — Recruiter Evaluates and Manages Candidates (Priority: P2)

**Goal**: Recruiters manage sourced and applied candidates, notes, reasons, status publication, and consent-checked contact/share actions.

**Independent Test**: Manage an applicant and sourced candidate, link without merging, reconcile stale edits, preview status publication, cancel Not relevant, and preview/confirm a minimum-data disclosure.

### Tests for User Story 4

- [x] T121 [P] [US4] Add candidate-work tests for first view/note/shortlist/status creation, contextual reuse, optional opening, and later application linking without merge in `app/tests/integration/recruiting/test_candidate_work_record.py`
- [x] T122 [P] [US4] Add status tests proving `/status-preview` accepts only `InternalRecruitingStatus` and returns a nullable `CandidateFacingStatus`, unmapped states return null, publication accepts only the eight-value `CandidateFacingStatus`, null suggestions cannot publish without an explicitly selected valid value, and recruiter confirmation, notification gating, and audit remain mandatory in `app/tests/contract/test_candidate_statuses.py`
- [x] T123 [P] [US4] Add note tests for exactly one owner, role access, tenant isolation, stale reconciliation, refresh persistence, and audit redaction in `app/tests/security/test_recruiter_notes.py`
- [x] T124 [P] [US4] Add Not relevant tests for structured reason/note requirement, cancellation restoring prior state, and contextual isolation in `app/tests/integration/recruiting/test_not_relevant.py`
- [x] T125 [P] [US4] Add contact/share tests for destination preview, minimum fields, current consent, cross-tenant denial, dual audit history, idempotency, and provider failure in `app/tests/security/test_candidate_disclosures.py`
- [x] T126 [P] [US4] Add browser tests for detail, notes, shortlist, status preview, conflict reconciliation, disclosure preview/confirmation, keyboard use, persistence, and mobile layout in `app/tests/browser/recruiter/candidate-management.spec.ts`

### Implementation for User Story 4

- [x] T127 [P] [US4] Create candidate-work, note, shortlist, status-event, and disclosure-request models with exact uniqueness and ownership constraints in `app/modules/recruiting/work_models.py`
- [x] T128 [US4] Generate candidate-work, note-owner XOR, shortlist, status-event, application-link, and disclosure migrations in `app/modules/recruiting/migrations/`
- [x] T129 [US4] Implement idempotent create-or-reuse candidate-work behavior for first authorized view, note, shortlist, or status mutation in `app/modules/recruiting/candidate_work.py`
- [x] T130 [US4] Implement application/candidate-work notes with object authorization, encryption, conflicts, persistence, and independent histories in `app/modules/recruiting/notes.py`
- [x] T131 [US4] Implement internal states/reasons, Not relevant cancellation, canonical eight-status mapping including Offered-to-`OFFER_MADE`, and null suggestions for Sourced, Not relevant, Hired, or unknown states in `app/modules/recruiting/statuses.py`
- [x] T132 [US4] Implement `InternalRecruitingStatus` preview-to-nullable-`CandidateFacingStatus` mapping and publication restricted to an explicitly selected valid eight-value `CandidateFacingStatus`, including null-suggestion rejection without selection, explicit confirmation, idempotent notification enqueue, and candidate-safe delivery-state projection in `app/modules/recruiting/status_service.py`
- [x] T133 [US4] Implement disclosure preview/confirmation with execution-time consent/object reauthorization, minimum fields, visible state, and dual audit history in `app/modules/recruiting/disclosures.py`
- [x] T134 [US4] Implement candidate detail, candidate-work, notes, shortlist, internal-status, status publication, and disclosure endpoints from OpenAPI in `app/modules/recruiting/views.py`
- [x] T135 [P] [US4] Build candidate detail, notes, shortlist, reasons, internal status, and status preview UI in `app/frontend/recruiter/candidate-detail.ts` and `app/frontend/templates/recruiter/candidate-detail.html`
- [x] T136 [P] [US4] Build destination/purpose/minimum-field disclosure preview, confirmation, pending, success, unavailable, and failure UI in `app/frontend/recruiter/disclosure.ts`
- [x] T137 [US4] Implement stored-versus-attempted conflict reconciliation in `app/frontend/shared/conflict-resolution.ts`
- [x] T138 [US4] Apply refresh persistence and unsaved-navigation warnings to notes, reasons, filters, shortlist selection, and status edits in `app/frontend/shared/persistence.ts`
- [x] T139 [US4] Add audit events for views, notes, shortlists, status, reasons, conflicts, disclosures, and notification overrides in `app/modules/recruiting/audit.py`
- [x] T140 [US4] Run and record sourced/applicant separation, status, Not relevant, persistence, and disclosure evidence in `docs/evidence/us4-candidate-management.md`

**Checkpoint**: US4 safely manages both contexts and completes the contact/share workflow without leaking candidate data.

---

## Phase 8: User Story 5 — Recruiter Compares a Shortlist (Priority: P2)

**Goal**: Recruiters compare consistent authorized evidence without generated recommendations or automated employment decisions.

**Independent Test**: Compare two or more candidates, handle no-selection and disappearing-selection states, then return to the preserved result context using keyboard and mobile layouts.

### Tests for User Story 5

- [x] T141 [P] [US5] Add comparison API tests for consistent fields, stable order, missing evidence, selection limits, disappearing candidates, and tenant/object authorization in `app/tests/contract/test_comparison_api.py`
- [x] T142 [P] [US5] Add browser tests for no selection, selecting/removing, side-by-side evidence, state preservation, focus return, keyboard use, 320px layout, and 200% zoom in `app/tests/browser/recruiter/comparison.spec.ts`
- [x] T143 [P] [US5] Add boundary tests proving comparison produces no generated recommendation and cannot reject, shortlist, contact, or change status in `app/tests/security/test_comparison_boundaries.py`

### Implementation for User Story 5

- [x] T144 [US5] Implement authorized deterministic comparison projections with consistent evidence, unknowns, and field ordering in `app/modules/recruiting/comparison.py`
- [x] T145 [US5] Implement the OpenAPI comparison endpoint with per-request reauthorization and no model-generated summary in `app/modules/recruiting/comparison_views.py`
- [x] T146 [P] [US5] Build accessible responsive comparison table/cards, empty guidance, missing-data labels, removal controls, and focus-return path in `app/frontend/recruiter/comparison.ts` and `app/frontend/templates/recruiter/comparison.html`
- [x] T147 [US5] Preserve comparison selection through allowed result interactions and remove newly unauthorized candidates with explanation in `app/frontend/recruiter/comparison.ts`
- [x] T148 [US5] Run and record comparison, preservation, and no-automation evidence in `docs/evidence/us5-comparison.md`

**Checkpoint**: US5 supports deterministic human comparison without the removed AI-summary feature.

---

## Phase 9: User Story 7 — Recruiter Organizes Hiring Work (Priority: P3)

**Goal**: Tenant users manage organization context, saved searches, audit metadata, and access reviews without changing tenant boundaries or gaining candidate-content access.

**Independent Test**: Use the foundational tenant/opening shell, add a visibly synthetic candidate, run/reopen an opening-linked search, inspect redacted audit metadata, and complete an access review and revocation.

### Tests for User Story 7

- [x] T149 [P] [US7] Add organization contract tests for unit/opening lifecycle, synthetic provenance, saved-search restoration/change detection, rejection of top-level client `opening_id`, sole use of `criteria.context.opening_id`, conflicts, and declared errors in `app/tests/contract/test_hiring_organization_api.py`
- [x] T150 [P] [US7] Add audit-access tests proving role redaction, no candidate content, non-enumeration, and an `AUDIT_READ` event for allowed/denied/failed access in `app/tests/security/test_audit_access.py`
- [x] T151 [P] [US7] Add access-review tests for memberships, privileged roles, purpose grants, emergency grants, audit access, independent review, revocation, exceptions, and overdue state in `app/tests/security/test_access_reviews.py`
- [x] T152 [P] [US7] Add Tenant Admin browser tests for organization, saved searches, redacted audit view, access review, and emergency notification/revocation in `app/tests/browser/admin/tenant-governance.spec.ts`

### Implementation for User Story 7

- [x] T153 [P] [US7] Create saved-search models referencing authoritative search criteria without an independently writable opening field, plus owner/version and `MEMBERSHIP|PRIVILEGED_ROLE|PURPOSE_GRANT|EMERGENCY_GRANT|AUDIT_ACCESS` review types in `app/modules/search/models.py` and `app/modules/tenancy/review_models.py`
- [x] T154 [US7] Generate saved-search constraints ensuring any derived opening index is server-maintained and equals `criteria.context.opening_id`, plus access-review constraints/indexes in `app/modules/search/migrations/` and `app/modules/tenancy/migrations/`
- [x] T155 [US7] Implement named saved searches separately from six recent searches, deriving opening context exclusively from `criteria.context`, rejecting independent client opening input, and detecting changes since save in `app/modules/search/saved_searches.py`
- [x] T156 [US7] Implement redacted audit queries whose allowed, denied, and failed reads emit minimized `AUDIT_READ` events in `app/modules/audit/query_service.py`
- [x] T157 [US7] Implement periodic access-review population, assignment, decision, exception expiry, revocation, and overdue escalation in `app/modules/tenancy/access_reviews.py`
- [x] T158 [US7] Implement saved-search endpoints that accept and return no top-level `opening_id`, plus redacted audit and access-review endpoints from OpenAPI in `app/modules/search/saved_views.py`, `app/modules/audit/views.py`, and `app/modules/tenancy/review_views.py`
- [x] T159 [P] [US7] Build organization, synthetic-candidate source label, opening, and saved-search management UI that submits no top-level `opening_id` and renders opening context only from `criteria.context` in `app/frontend/recruiter/organization.ts` and `app/frontend/templates/recruiter/organization.html`
- [x] T160 [P] [US7] Build redacted audit and access-review UI without candidate-content rendering in `app/frontend/admin/access-review.ts` and `app/frontend/templates/admin/access-review.html`
- [x] T161 [P] [US7] Build emergency-access notification, scope, expiry, and revoke UI without candidate content in `app/frontend/admin/emergency-access.ts` and `app/frontend/templates/admin/emergency-access.html`
- [x] T162 [US7] Emit minimized audit events for organization changes, synthetic records, saved searches, audit reads, reviews, and revocations in `app/modules/tenancy/audit.py`
- [x] T163 [US7] Run and record tenant-governance, organization, audit-access, and access-review evidence in `docs/evidence/us7-hiring-organization.md`

**Checkpoint**: US7 completes organization and governance workflows without weakening tenant or candidate-content boundaries.

---

## Frontend Migration: after Phase 9, before Phase 10

Approved 2026-10-01. Normative route/component/API/state/test/fallback details for every phase are in [frontend-migration.md](./frontend-migration.md). Preserve all existing task completion marks. Each phase is test-first: define/capture acceptance coverage, implement the slice, verify before cutover. Every task remains unchecked until implementation and acceptance pass. FM task IDs are a dedicated namespace, not replacements for T001–T206.

### FM1: Reconcile WIP and capture baselines

- [X] FM1-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: Phase 9 / T163 and prior completed amendments.
- [X] FM1-02 Reconcile every file in checkpoint 66a3acd and any new WIP against 5372072; record reuse/rework decisions, build/security/accessibility/regression verification, original mockup hash, font/logo checks and verified legacy fallback; do not assume committed WIP is correct. Dependency: FM1-01.
- [X] FM1-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; retain legacy defaults without page cutover. Dependency: FM1-02.

FM1 evidence: [reconciliation and verification](../../docs/evidence/frontend-migration/fm1.md). FM1-03 blockers resolved in the authorized follow-up: trusted tenant bootstrap, provenance-safe recent cleanup, landmark remediation and manual keyboard/screen-reader-oriented review. Full regression passes; no WIP page is approved for cutover. FM2 dependency gate is cleared, but FM2 has not begun. Missing approved branding assets use the documented temporary fallback and are not a blocker.

### FM2: React/Tailwind foundation and design system

- [X] FM2-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM1-03.
- [X] FM2-02 Implement react/tailwind foundation and design system within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM2-01.
- [X] FM2-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; retain legacy defaults without page cutover. Dependency: FM2-02.

FM2 evidence: [foundation and verification](../../docs/evidence/frontend-migration/fm2.md). Shared components, isolated showcase, 15 visual goldens, transport/mount/manifest checks and complete regression pass. Empty route registry and default-off flags remain unchanged. FM3 is not started; the FM1–FM14 umbrella checklist remains unchecked.

### FM3: Global shell and signed-out chooser

- [X] FM3-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM2-03.
- [X] FM3-02 Implement global shell and signed-out chooser within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM3-01.
- [X] FM3-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM3-02.

FM3 security clarification (2026-10-01): FM3-01 includes publication/withdrawal,
draft/closed/expired exclusion, synchronization failure, field minimization,
cross-tenant non-inference, bounded pagination/rate limits and non-owner,
NOBYPASSRLS PostgreSQL tests. FM3-02 includes the explicitly approved separate
PublicOpeningProjection and necessary migration/private source linkage,
transactional authorized publication with minimized audits, restricted endpoint
reads, and projection-backed public role resolution. Never add an anonymous
policy to recruiting_opening or change its forced RLS. No automatic source
backfill. FM3-03 must verify these security gates plus chooser navigation and
legacy rollback. This clarification does not authorize FM4 or Phase 10.

FM3 evidence: [security, visual and regression verification](../../docs/evidence/frontend-migration/fm3.md).
295 PostgreSQL tests collected (294 pass, one expected skip), 53 browser tests
passed across the complete regression batches, repository-wide typing and quality
checks pass. Only the chooser is eligible for server opt-in; all route flags remain
default-off. The minimal public jobs destination remains Django-rendered. FM4 is
cleared but not started; the FM1–FM14 umbrella item remains unchecked.

### FM3 remediation: Independent publication (owner approved 2026-10-01)

- [X] FM3-R01 Add test-first independent publication/lifecycle, authorization, ETag/digest, idempotency, failure, restricted-role and browser tests in `app/tests/contract/test_opening_publication.py`, `app/tests/database/test_public_opening_projection.py` and `app/tests/browser/recruiter/opening-publication.spec.ts`. Dependency: FM3-03 and approved contract amendment.
- [X] FM3-R02 Extend the existing service with confirmed independent publication/withdrawal, a projection revision migration, contract operations and compact legacy controls in `app/modules/recruiting/`, `app/frontend/recruiter/opening-publication.ts` and `app/frontend/recruiter/organization.ts`; align planning/contracts. Dependency: FM3-R01 failing acceptance evidence.
- [X] FM3-R03 Record publish → /jobs/ → withdraw verification, accessibility, focused checks and one complete regression pass in `docs/evidence/frontend-migration/fm3.md`; preserve flags, mockup, prior tests and unchecked umbrella gate. Dependency: FM3-R02. FM4 is gated on this remediation, not the earlier completion statement.

### FM4: Recruiter search home/sidebar

Explicit security clarification (2026-10-01): FM4-to-legacy transport uses a
dedicated encrypted, typed, session-bound handoff, never browser storage or a
general JSON session store. FM4-02 is additionally gated on FM4-R03. FM5/FM6 UI
migration remains out of scope; the shared search route remains default-off.

- [X] FM4-R01 Add test-first typed handoff, session/actor/tenant/target binding, expiry/revocation/completion, CSRF, concurrency, rate-limit, log/audit minimization, restricted-role forced RLS and recent-search authorization tests. Dependency: FM3-R03 and explicit handoff authorization.
- [X] FM4-R02 Implement encrypted SearchWorkflowHandoff, forced tenant RLS migration, typed create/restore/revise/revoke operations, metadata-only restoration, separate authorized persisted-result display read, bounded cleanup and recent-search GET operations; align plan/model/OpenAPI/authorization/events. Dependency: FM4-R01 failing tests.
- [X] FM4-R03 Replace legacy criteria/results browser-storage transport with opaque-fragment/server restore; verify all 24 remediation cases, refresh/back/sign-out, browser-storage absence and same-URL rollback. No legacy UI migration. Dependency: FM4-R02. FM4-01–03 completion requires passing this security gate.

- [X] FM4-R04 Test ordered comparison-selection transport, binding/target isolation, source membership/current consent, 409 concurrency, ten-item limit, no recruiting side effects, CSRF/rate limits, RLS and minimized auditing. Dependency: FM4-R02 and explicit comparison-transport authorization.
- [X] FM4-R05 Extend the encrypted handoff with comparison-selection, typed create/read/replace/revoke and server-generated return operation; replace legacy selection persistence without UI migration. Dependency: FM4-R04 failing tests.
- [X] FM4-R06 Verify all 25 comparison remediation cases, refresh/Back/return/focus, absence of protected browser storage and the complete chained authenticated journey; run full regression evidence before any completion/cutover. Dependency: FM4-R05; gates FM4-R03 and FM4-03. FM5 scope is unchanged.

- [X] FM4-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM3-03.
- [X] FM4-02 Implement recruiter search home/sidebar within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM4-01.
- [X] FM4-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM4-02.

FM4 evidence: [final verification](../../docs/evidence/frontend-migration/fm4.md).
345 PostgreSQL tests passed (one existing trigger-fixture skip); all 60 browser tests
passed with authenticated gates enabled. Search home is verified locally behind its
default-off flag; production remains legacy. FM5 and the umbrella gate remain unchecked.

### FM5: Criteria review

- [X] FM5-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM4-03.
- [X] FM5-02 Implement criteria review within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM5-01.
- [X] FM5-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM5-02.

FM5 evidence: [criteria-review verification](../../docs/evidence/frontend-migration/fm5.md).
The criteria-review-page server flag remains absent/default-off as requested; only
the isolated verification process enabled it. Same-URL legacy rollback, existing
handoffs and all prior tests remain intact. FM6's dependency is cleared, but FM6
has not started and the FM1–FM14 umbrella remains unchecked.

### FM6: Results and candidate detail

Approved direct-results amendment: FM6-01 includes positive direct Search → Results,
negative inline clarification/no-execution, applied-criteria chips and in-results edits.
FM6-02 reconciles home/legacy transport and existing tests, restores committed flags off,
and exposes authorized source criteria through existing SEARCH_RESULTS metadata. FM6-03
requires full regression and both renderer modes. No mandatory standalone review remains
in the normal journey; retain internal fallback coverage. No FM7 scope is added.

- [X] FM6-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM5-03.
- [X] FM6-02 Implement results and candidate detail within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM6-01.
- [X] FM6-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; retain all production flags default-off under the approved rollout decision. Dependency: FM6-02.

FM6 evidence: [results and direct-search verification](../../docs/evidence/frontend-migration/fm6.md).
350 PostgreSQL tests pass (one existing skip; 351 collected), all 79 browser tests pass
with authenticated gates enabled, repository-wide typing and all quality/build gates pass.
Search input → Search → Results is normal; uncertain interpretation stays inline and
results owns applied-criteria adjustments. Standalone candidate management remains legacy
under the shared FM7 route gate. All committed flags and the umbrella checklist remain off.
FM7 is cleared but not started.

### FM7: Recruiter management and disclosure UI

- [X] FM7-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM6-03.
- [X] FM7-02 Implement recruiter management and disclosure ui within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM7-01.
- [X] FM7-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM7-02.

FM7 evidence: [management and disclosure verification](../../docs/evidence/frontend-migration/fm7.md).
353 PostgreSQL tests pass (one existing skip; 354 collected); all 90 browser tests
pass with authenticated gates enabled. Repository-wide typing, quality and all four
builds pass. Per the explicit rollout decision, verification flags were process-local
only: all committed React flags remain default-off and same-URL legacy rollback is
preserved. The umbrella checklist remains unchecked. FM8 is unstarted.

### FM8: Candidate comparison

- [ ] FM8-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM7-03.
- [ ] FM8-02 Implement candidate comparison within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM8-01.
- [ ] FM8-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM8-02.

### FM9: Candidate profile and resume flow

- [ ] FM9-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM8-03.
- [ ] FM9-02 Implement candidate profile and resume flow within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM9-01.
- [ ] FM9-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM9-02.

### FM10: Public jobs, role and application

- [ ] FM10-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM9-03.
- [ ] FM10-02 Implement public jobs, role and application within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM10-01.
- [ ] FM10-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM10-02.

### FM11: Candidate progress and rights

- [ ] FM11-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM10-03.
- [ ] FM11-02 Implement candidate progress and rights within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM11-01.
- [ ] FM11-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM11-02.

### FM12: Recruiter organization/openings

- [ ] FM12-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM11-03.
- [ ] FM12-02 Implement recruiter organization/openings within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM12-01.
- [ ] FM12-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM12-02.

### FM13: Tenant Admin governance

- [ ] FM13-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM12-03.
- [ ] FM13-02 Implement tenant admin governance within the approved route/component/API boundaries; apply exclusive DOM ownership, semantic tokens and protected-state handling. Dependency: FM13-01.
- [ ] FM13-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; enable only this phase's verified route replacements. Dependency: FM13-02.

### FM14: Full parity, accessibility and regression verification

- [ ] FM14-01 Capture acceptance tests and evidence for this phase's exact routes, states, keyboard/screen-reader behavior, four viewports and zoom; preserve prior security tests. Dependency: FM13-03.
- [ ] FM14-02 Run full PostgreSQL collection/suite, mypy ., Ruff, Django/migration checks, frontend checks/build and complete authenticated Playwright/accessibility/visual suites; prove no deleted tests or reduced type scope. Dependency: FM14-01.
- [ ] FM14-03 Record passing functional, authorization, accessibility, screenshot and build evidence; verify both renderers and rollback; approve migration completion only with no unexplained drift; Phase 10 stays deferred until this gate passes. Dependency: FM14-02.

## Phase 10: Production Hardening, Manual Review, and Release Evidence

Deferred: requires FM14-03. No production-hardening work begins during frontend migration.

**Purpose**: Validate accessibility, usability, privacy, incident response, security, AI promotion, recovery, scale, and existing-functionality preservation.

- [ ] T164 [P] Create AWS network, regional WAF/ALB, ECS/Fargate, private subnets/endpoints, and multi-AZ topology in `infra/environments/production/main.tf` and `infra/modules/platform/`
- [ ] T165 [P] Configure CloudFront only for versioned public static assets and explicitly deny authenticated routes, HTML, APIs, uploads, downloads, exports, and candidate content in `infra/modules/platform/cloudfront.tf`
- [ ] T166 [P] Create encrypted RDS/pgvector, Valkey, S3 quarantine/clean/export buckets, deletion policies, and cross-account audit storage in `infra/modules/data/`
- [ ] T167 [P] Configure Cognito, SES, CloudWatch, OpenTelemetry, Security Hub, GuardDuty, CloudTrail, Config, and alert routing in `infra/modules/security/` and `infra/modules/observability/`
- [ ] T168 Configure point-in-time recovery for 15-minute RPO, encrypted 35-day backups, quarterly restore automation, and four-hour RTO in `infra/modules/recovery/` and `docs/runbooks/disaster-recovery.md`
- [ ] T169 Define 99.9% availability, p95 search under three seconds, queue/rights/audit/security signals, and browser interaction budgets in `docs/operations/slos.md` and `infra/modules/observability/alarms.tf`
- [ ] T170 [P] Add million-profile/100-tenant/1,000-user fixtures and search/load scenarios in `app/tests/load/data.py` and `app/tests/load/search.js`
- [ ] T171 Run capacity tests and record p50/p95/p99 latency, saturation, errors, isolation, audit, and remediation in `docs/evidence/capacity-and-performance.md`
- [ ] T172 [P] Add failure injection for identity, authorization, database, storage, scan, parser, model, email, WhatsApp, queue, cache, and audit sink in `app/tests/resilience/test_failure_matrix.py`
- [ ] T173 [P] Add stale-write tests for consent, visibility, status, note, and administration reconciliation in `app/tests/integration/test_concurrency.py`
- [ ] T174 [P] Add retention tests for renewal, inactivity deletion, all required `ActiveProcessRetentionException` fields and version/lifecycle transitions, terminating-event deletion resumption, legal-hold separation, snapshot/export expiry, and backup propagation in `app/tests/integration/test_retention.py`
- [ ] T175 [P] Add automated axe, keyboard, focus, semantic, live-region, contrast, zoom, and reduced-motion checks for every critical page in `app/tests/accessibility/critical-flows.spec.ts`
- [ ] T176 Conduct post-implementation manual keyboard, representative screen-reader, 200% zoom, high-contrast, reduced-motion, touch/pointer, long-content, and 320px-through-desktop review in `docs/evidence/manual-accessibility-review.md`
- [ ] T177 Remediate and manually re-test every accessibility finding, blocking release on unresolved Level A/AA or critical-flow failures in `docs/evidence/manual-accessibility-remediation.md`
- [ ] T178 [P] Add viewport and visual regression against the approved mockup without modifying the source mockup in `app/tests/browser/regression/mockup-preservation.spec.ts`
- [ ] T179 [P] Add end-to-end tests for conditional visibility/deletion/emergency access, `AD_HOC` versus active-opening `OPENING` search, grouped `ANY|ALL` criteria, eight-status applications, candidate-safe notification states, retention exceptions, candidate management/disclosure, comparison, organization, and audit reviews in `app/tests/e2e/critical-journeys.spec.ts`
- [ ] T180 [P] Add instrumented browser assertions that navigation, save, filtering, and status feedback begins within one second in `app/tests/browser/performance/interaction-feedback.spec.ts`
- [ ] T181 [P] Add SAST, secret, dependency, container, IaC, SBOM-signing, and severity gates in `.github/workflows/security.yml`
- [ ] T182 Add authenticated and unauthenticated OWASP ZAP DAST against production-topology staging with blocking triage rules in `.github/workflows/dast.yml` and `app/tests/security/zap-rules.tsv`
- [ ] T183 Conduct threat modeling for tenant escape, IDOR, malware, prompt injection, disclosure, status misuse, support abuse, and emergency access in `docs/security/threat-model.md`
- [ ] T184 Run model-promotion evaluation for schema/citation quality, protected-trait/proxy leakage, fairness, injection, privacy/residency, lifecycle, latency, cost, and fallback in `docs/evidence/ai-model-promotion.md`
- [ ] T185 Commission and close an independent penetration-test remediation log before real candidate data in `docs/security/penetration-test-remediation.md`
- [ ] T186 Write the candidate-data incident runbook covering detection, triage, containment, evidence, India notification decisions/approval, tenant/candidate communications, recovery, and post-incident testing in `docs/runbooks/candidate-data-incident-response.md`
- [ ] T187 Execute a candidate-data incident tabletop exercise, close findings, and retain participant/decision/timing evidence in `docs/evidence/candidate-data-incident-exercise.md`
- [ ] T188 Execute a pre-release access review for memberships, privileged roles, purpose grants, emergency grants, and audit access; record revocations and expiring exceptions in `docs/evidence/pre-release-access-review.md`
- [ ] T189 Create migration rehearsal, reversible expand/migrate/contract steps, mockup route strangling, and rollback criteria in `docs/runbooks/migration-and-rollback.md`
- [ ] T190 Define feature flags, synthetic-only environments, pilot controls, launch gates, incident rollback, and no-real-data approval in `docs/runbooks/rollout.md`
- [ ] T191 [P] Create moderated usability protocols covering SC-001, SC-002 timing, SC-003, SC-005, SC-007, SC-008, SC-012, and privacy-rights tasks in `docs/usability/moderated-test-protocol.md`
- [ ] T192 Execute moderated candidate testing for timed profile preview, visibility, application progress, and privacy rights in `docs/evidence/moderated-candidate-usability.md`
- [ ] T193 Execute moderated recruiter testing for search intent, explanations, comparison, notes, disclosure, and status publication in `docs/evidence/moderated-recruiter-usability.md`
- [ ] T194 Remediate usability findings and rerun failed scenarios to specified thresholds in `docs/evidence/moderated-usability-remediation.md`
- [ ] T195 Perform India legal/privacy review for notices, consent, disclosures, processors, rights, active-process policy, retention, incidents, and WhatsApp in `docs/compliance/india-launch-review.md`
- [ ] T196 Restore an isolated 35-day encrypted backup and verify data integrity, tenant isolation, authorization, and audit continuity in `docs/evidence/backup-restore-exercise.md`
- [ ] T197 Replay deletion, consent-withdrawal, tenant-access-revocation, and emergency-grant-revocation events through the recovery point before enabling restored access in `docs/evidence/deletion-event-replay.md`
- [ ] T198 Execute regional recovery/failover and prove no more than 15 minutes loss and four hours recovery after replay in `docs/evidence/recovery-exercise.md`
- [ ] T199 Run the complete quickstart and launch gates, recording commands, versions, outcomes, waivers, and approvers in `docs/evidence/production-readiness.md`

**Checkpoint**: Production remains blocked until every required gate has passing evidence or an authorized, bounded constitution exception.

---

## Dependencies and Execution Order

### Phase Dependencies

1. **Setup** starts immediately.
2. **Foundation** follows Setup and delivers the tenant/business-unit/opening shell before search or applications.
3. **US1** follows Foundation and is the synthetic-data MVP.
4. **US2** follows Foundation plus the opening shell; production Matching roles and candidate findings also require US1 visibility and T201 employment records.
5. **US3** follows US2 search execution.
6. **US6** follows US1 and the opening shell and creates application behavior before applicant-management integration.
7. **US4** follows US2 and US6 so sourced records can link to implemented applications without merging.
8. **US5** follows US2 and US4 because comparison consumes authorized result and shortlist state.
9. **US7** follows the shared shell and US2 because saved-search restoration uses implemented searches; its audit/access-review work is otherwise independent.
10. **Frontend migration** follows Phase 9: FM1 → FM2 → FM3 → FM4 → FM5 → FM6 → FM7 → FM8 → FM9 → FM10 → FM11 → FM12 → FM13 → FM14. Each phase gates the next; FM3 supplies the minimum real jobs destination before FM10 visual completion.
11. **Production hardening** follows FM14-03; earlier infrastructure/protocol authoring is deferred by the approved migration sequence.

### Dependency Graph

```text
Setup → Foundation (tenant/business-unit/opening shell) → US1 (MVP)
                     ├─→ US2 → US3
                     ├─→ US6 ─┐
                     └─────────┴→ US4 → US5
                          US2 ───────→ US7 saved-search integration

All launch stories → FM1–FM14 → deferred Phase 10 manual accessibility + incident + access review + DAST/AI + restore/replay gates
```

### Parallel Opportunities

- Setup tasks marked `[P]` can run concurrently after T004 establishes directories.
- Foundation policy, operations, audit, communications, infrastructure, and test files marked `[P]` can proceed in parallel after shared models stabilize.
- Tests marked `[P]` within a story can be authored together before implementation.
- After Foundation, US1 and the non-search parts of US7 may proceed alongside US2 using synthetic fixtures, but the numbered integration order remains authoritative.
- Production-hardening infrastructure and protocols remain deferred until FM14-03. Within frontend migration, only independent acceptance checks in the current phase may run concurrently.

---

## Implementation Strategy

### Recommended MVP

Complete **Setup + Foundation + US1** and demonstrate with synthetic data only. This validates candidate control, resume safety, privacy rights, accessibility, and the tenant/opening security foundation before recruiter discovery is enabled.

### Incremental Delivery

1. Setup and Foundation, including platform-only tenant and active-opening prerequisites.
2. US1 candidate-control MVP.
3. US2 deterministic search, then US3 criteria review.
4. US6 applications and progress.
5. US4 sourced/applicant management and disclosures, then US5 comparison.
6. US7 saved searches, audit access, and access reviews.
7. Complete every production hardening and pre-release evidence task.

### Deferred Features

- **Real recruiter-entered candidate records** are deferred; launch supports only visibly synthetic tenant fixtures. Enabling real recruiter-entered people requires a separate specification and privacy review.
- **WhatsApp delivery** remains disabled until provider, residency, templates, consent, and callbacks are approved; the UI exposes unavailable/pending state.
- **AI-dependent enhancements** remain feature-flagged off until T184 promotion evidence passes. Core resume entry, criteria review, search, and comparison remain deterministic/manual.
- **AI-generated comparison summaries are not in launch scope** and have no implementation task.

### Scope Discipline

- Preserve `enter_recruiter_recruiter_candidate_ux.html` as a read-only baseline.
- Keep eligibility, authorization, status publication, disclosures, and employment decisions deterministic and human-controlled.
- Keep `SHORT_TENURE` informational and post-ranking; it must never alter eligibility, visibility, score, rank, recommendation, application status, hiring outcome, or trigger an automated action.
- Do not accept real candidate data until privacy, legal, accessibility, security, incident, access-review, backup/replay, recovery, and production-readiness gates pass.
- Retain failing-then-passing evidence for tests and manual evidence for constitution-required reviews.
