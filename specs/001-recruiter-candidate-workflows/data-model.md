# Data Model: Recruiter and Candidate Workflows

## FM4 SearchWorkflowHandoff (explicit security clarification)

Approved extension: `comparison-selection` uses the same forced-RLS encrypted
table, adding `updated_at` and a separate target kind (migration 0007). Payload
permits only schema version, source search UUID and ordered unique candidate UUIDs
(0–10). No URL/token is persisted. Current source snapshots, visibility, consent and
comparison field scope are revalidated for create/read/replace. Same credential,
actor, tenant, expiry and optimistic version rules apply. Final comparison still
uses its existing authorization service, independently of selection transport.

Dedicated tenant-RLS table: UUID, tenant, actor, SessionCredential, kind
(`criteria-review`/`search-results`), unique token SHA-256, retry/request hashes,
encrypted payload, source version hash, nullable WorkflowRun/SearchDefinition
reference selected by kind, state (`ACTIVE`/`REVOKED`/`COMPLETED`), optimistic version,
created_at and expires_at. Credential/retry hash is unique. Source deletion deletes
the transient record, never the reverse. Maximum lifetime is fifteen minutes.

Payload schema v1 permits only structured validated criteria for review, or persisted
search UUID for results. No prompt, candidate record, result copy or arbitrary UI
JSON. Result-context version hashes canonical criteria and persisted snapshot IDs.
Workflow version hashes its ID, update timestamp and status. Existing versioned
field encryption/key management is reused. Forced tenant RLS does not replace
actor/session/opening checks. No changes to source WorkflowRun/SearchRun RLS.

**Date**: 2026-09-28  
**Database**: PostgreSQL 16 with RLS, `pg_trgm`, full-text search, and `pgvector`.

## Modeling Rules

- A verified email maps to one candidate-controlled profile. Store normalized email as a keyed HMAC for uniqueness/lookups and encrypted display email separately.
- Tenant-owned rows always contain `tenant_id`; application code must not accept tenant identity from an untrusted request body.
- Cross-tenant reads are denied unless a current, purpose-specific candidate grant covers the actor, tenant, fields, object, and operation.
- Candidate profile data and tenant application data have separate ownership and retention boundaries.
- Sensitive text uses application-level envelope encryption where field-level isolation is required; all storage also uses AWS KMS encryption at rest.
- Mutable safety-critical aggregates contain `version`, `created_at`, `updated_at`, and `updated_by`. Changes also create immutable history/audit rows.
- Timestamps are UTC. External identifiers are non-sequential UUIDv7.
- Hard privacy deletion cascades to source, projection, embedding, cache, export, and workflow checkpoint; a non-identifying deletion receipt remains.

## Entity Relationships

```text
Identity ──< TenantMembership >── Tenant ──< BusinessUnit ──< Opening
    │                                  │          │              │
    │                                  ├──< Search ──< CandidateWorkRecord
    │                                  ├──< RecruiterEnteredCandidate
    │                                  ├──< AccessReview
    │                                  └──< Application >── CandidateProfile
    │                                               │
    └── CandidateProfile ──< ResumeAsset            ├──< ApplicationStatusEvent
              │              └──< ExtractedFact     ├──< RecruiterNote
              ├──< EmploymentRecord ──< CandidateFinding
              ├──< ConsentRecord                    └──< Notification
              ├──< VisibilityRule
              ├──< DisclosureRequest
              ├──< DataRightsRequest ──< ActiveProcessRetentionException >── Application
              └──< ProfileEvidence ──< EvidenceEmbedding

AccessGrant / EmergencyAccessRequest gate exceptional reads.
AuditEvent and OutboxEvent record security/business effects across aggregates.
```

## Identity, Authorization, and Tenancy

### `identity`

| Field | Type | Constraints / purpose |
|---|---|---|
| `id` | uuid | PK |
| `cognito_subject` | text | Unique, immutable external subject |
| `email_lookup_hmac` | bytea | Unique for verified email lookup; never displayed |
| `email_ciphertext` | bytea | Encrypted canonical email |
| `email_verified_at` | timestamptz | Required before candidate merge or workforce access |
| `status` | enum | `ACTIVE`, `SUSPENDED`, `CLOSED` |
| `last_authenticated_at` | timestamptz | Lifecycle/security signal |

### `tenant`

| Field | Type | Constraints / purpose |
|---|---|---|
| `id` | uuid | PK |
| `name`, `slug` | text | Unique active slug |
| `status` | enum | `PROVISIONING`, `ACTIVE`, `SUSPENDED`, `CLOSED` |
| `default_timezone` | text | IANA name; default `Asia/Kolkata` |
| `retention_policy_version` | text | Policy applied to tenant records |
| `version` | bigint | Optimistic concurrency |

Tenants are provisioned only by the audited platform-onboarding function. One tenant represents one contracted customer company or legally separate recruiting boundary; users cannot create or alter tenant boundaries through recruiting administration.

### `business_unit`

Tenant-owned organizational context with `id`, `tenant_id`, required name, optional description/reference, `ACTIVE|INACTIVE` status, version, creator, and timestamps. Business units organize openings but are never authorization-isolation boundaries.

### `tenant_membership`

| Field | Type | Constraints / purpose |
|---|---|---|
| `tenant_id`, `identity_id` | uuid | Composite unique membership |
| `role` | enum | `RECRUITER`, `HIRING_MANAGER`, `TENANT_ADMIN` |
| `status` | enum | `INVITED`, `ACTIVE`, `SUSPENDED`, `REVOKED` |
| `scope` | jsonb | Opening/team restrictions; validated schema |
| `version` | bigint | Reject stale administration changes |

Candidate and Platform Security Admin roles are global identity capabilities, never tenant memberships. A user may hold memberships in multiple tenants but one request operates under exactly one selected tenant context.

### `access_grant`

Purpose-specific candidate consent or object permission. Fields: `candidate_profile_id`, optional `tenant_id`, `grantee_type`, `grantee_id`, `purpose_code`, `field_scope`, `object_scope`, `valid_from`, `expires_at`, `status`, `consent_record_id`, `revoked_at`, `version`.

### `emergency_access_request`

Fields: requesting Platform Security Admin, reason code and stated justification, exact tenant/object/field/read-operation scope, requested duration, incident/ticket reference, status, approving designated Platform Security Admin, approval/rejection timestamps, automatic expiry, revocation actor/time, affected-Tenant-Admin notification evidence, and `used_at`. The requester cannot approve their own request. Maximum default duration is one hour; extension requires a new request and peer approval. An affected Tenant Admin may revoke without receiving candidate-content access.

## Candidate-Owned Data

### `candidate_profile`

| Field | Type | Constraints / purpose |
|---|---|---|
| `id` | uuid | PK |
| `identity_id` | uuid | Unique FK: one profile per verified identity/email |
| `full_name` | encrypted text | Required to publish |
| `location` | structured jsonb | Normalized plus candidate display text |
| `headline`, `current_role`, `current_company` | text | Candidate-reviewable facts |
| `experience_years` | numeric(5,2) | Required to publish; zero and fractional values allowed, negative values rejected |
| `work_arrangements` | enum array | Candidate-controlled `FLEXIBLE|REMOTE|HYBRID|ON_SITE` preferences |
| `role_categories`, `preferred_locations` | structured values | Candidate-controlled deterministic matching eligibility |
| `meaningful_work` | varchar(300) | Enforced length |
| `notice_period`, `availability_date` | typed fields | Candidate-controlled |
| `compensation` | encrypted structured value | Currency + integer minor unit; restricted scope |
| `profile_state` | enum | `DRAFT`, `REVIEW_REQUIRED`, `PUBLISHED`, `HIDDEN`, `DELETION_PENDING`, `DELETED` |
| `last_candidate_activity_at` | timestamptz | Drives 12-month inactivity |
| `consent_expires_at` | timestamptz | Nullable only while draft/active exception applies |
| `version` | bigint | `ETag`; reject stale consent/visibility/profile writes |

### `candidate_skill`

Candidate-owned normalized skill with `candidate_profile_id`, normalized/display name, optional level/years, provenance, candidate review state, ordering, validity timestamps, and uniqueness per normalized skill. Skills are required to publish but may remain explicitly self-reported or unknown in optional detail.

### `candidate_contact`

Encrypted optional phone/WhatsApp and other approved contact channels with verification, purpose/field visibility, consent, and timestamps. Email remains on `identity`; no contact value is placed in URLs, logs, or search projections.

### `profile_link`

Candidate-controlled professional link with normalized URL, display label, verification state, and ordering. Never infer protected characteristics from link content.

### `employment_record`

Candidate-controlled employment history. Fields: `id`, `candidate_profile_id`, company, optional
role title, nullable start/end date values, per-date state (`CONFIRMED`, `SUGGESTED`, `AMBIGUOUS`,
`MISSING`),
`is_current`, employment type (`PERMANENT`, `INTERNSHIP`, `APPRENTICESHIP`,
`FIXED_TERM_CONTRACT`, `CONSULTING`, `SEASONAL`, `OTHER_TEMPORARY`, `OTHER`, `UNKNOWN`), employment-
type review state, provenance, extraction confidence/source spans, ordering, `version`, and
timestamps. End date must be null for a current role. A non-current record may remain incomplete for
candidate correction, but it is eligible as a confirmed completed record only when both dates are
complete and confirmed and the end is on or after the start; otherwise its finding evaluation is
`INSUFFICIENT_DATA`. Extraction suggestions never become confirmed until candidate
acceptance/correction and never synthesize absent values or a departure reason.

### `visibility_rule`

Fields: `candidate_profile_id`, mode (`APPROVED_RECRUITERS`, `MATCHING_ROLES`, `APPLIED_ROLES_ONLY`, `NOT_LOOKING`), approved-tenant scope, deterministic matching-preference snapshot, effective timestamps, superseded record, policy version, actor, and consent record. Changes are append-only; `candidate_profile` references the current rule. A check/service invariant requires a non-empty approved-tenant scope for `APPROVED_RECRUITERS` and non-empty deterministic preferences for `MATCHING_ROLES`. `MATCHING_ROLES` additionally requires an active `OPENING` search before retrieval; `APPLIED_ROLES_ONLY` requires a submitted application and current hiring-team authorization.

### `consent_record`

Immutable evidence: candidate, purpose, field/data scope, audience/tenant scope, notice version, affirmative action, locale, captured time, expiry, withdrawal, and source request ID. Do not store raw IP as consent proof beyond approved security retention; use a minimized network token if required.

### `resume_asset`

| Field | Type | Constraints / purpose |
|---|---|---|
| `id`, `candidate_profile_id` | uuid | PK/FK |
| `quarantine_key`, `clean_key` | text | Opaque S3 keys; never user filenames |
| `original_filename_ciphertext` | bytea | Encrypted display-only name |
| `declared_mime`, `detected_mime`, `size_bytes`, `sha256` | scalar | Validation and duplicate detection |
| `scan_status`, `parse_status` | enum | State machines below |
| `scan_provider_ref` | text | Non-sensitive correlation |
| `is_current` | boolean | Unique current resume per profile |
| `retention_until`, `deleted_at` | timestamptz | Lifecycle |
| `version` | bigint | State transition concurrency |

### `extracted_fact`

Fields: resume, fact type, normalized candidate value, encrypted source excerpt if necessary, page/offset reference, confidence band, extraction method/model version, state (`SUGGESTED`, `ACCEPTED`, `CORRECTED`, `REJECTED`), reviewer, and timestamp. Publication uses only accepted/corrected values.

### `profile_evidence` and `evidence_embedding`

`profile_evidence` stores a minimal, provenance-linked, candidate-approved search fact. It identifies fact type, normalized value, self-reported/inferred status, source, confidence, visibility scope, and validity dates. `evidence_embedding` stores model/version, 512-dimensional vector, content hash, and indexing state. It contains no tenant-private note.

### `candidate_finding`

Generic derived evaluation linked to `candidate_profile_id`, `source_record_type`, and
`source_record_id`. Fields: `id`, code (initially `SHORT_TENURE`), severity (`INFORMATIONAL`), result
(`FOUND`, `NOT_FOUND`, `INSUFFICIENT_DATA`, `EXCLUDED`), evidence JSON, deterministic message key,
calculation version, source-record version, evaluated time, superseded time, and lifecycle/audit
references. The `SHORT_TENURE` evidence contains the employment-record ID, company, confirmed start
and end values, calculated duration (`calendar_months` plus remaining days), calculation version, and
evaluation timestamp; it never stores or infers a reason for leaving. A unique active evaluation per
`(candidate_profile_id, code, source_record_type, source_record_id, calculation_version)` supports
multiple qualifying employment records without duplicates.

The evaluator compares a confirmed completed record's end date to its start date plus 12 calendar
months. `end_date < start_date + 12 calendar months` yields `FOUND` unless the explicit employment
type is internship, apprenticeship, fixed-term contract, consulting, seasonal, or other temporary,
which yields `EXCLUDED`. Current records yield `NOT_FOUND`; incomplete or ambiguous dates yield
`INSUFFICIENT_DATA`. Only active `FOUND` evaluations are recruiter-visible. Findings are attached to
an already authorized result/detail projection after eligibility, scoring, and ordering and have no
foreign key or service write path to ranking, recommendation, application status, or hiring outcome.

## Recruiting Data

### `opening`

Tenant-owned role linked to a required business unit: title, location/work mode, employment type, compensation range, description, hiring team, state (`DRAFT`, `OPEN`, `PAUSED`, `CLOSED`), and `version`.

### `application`

| Field | Type | Constraints / purpose |
|---|---|---|
| `id`, `tenant_id`, `opening_id`, `candidate_profile_id` | uuid | Unique `(opening_id, candidate_profile_id)` |
| `candidate_work_record_id` | uuid nullable | Optional link to prior sourced context; never implies state/history merge |
| `state` | enum | Internal workflow state |
| `candidate_status` | `CandidateFacingStatus` | Published candidate-facing status; initialized to `APPLIED` on successful submission |
| `suggested_candidate_status` | `CandidateFacingStatus` nullable | Unpublished mapping suggestion; null for unmapped internal states |
| `status_published_at/by` | values | Explicit recruiter confirmation evidence |
| `answers` | jsonb/encrypted | Versioned schema and per-application responses |
| `consent_context_id` | uuid | Consent snapshot for this role |
| `submitted_at`, `withdrawn_at`, `closed_at` | timestamptz | Independent lifecycle |
| `version` | bigint | Reject stale status/application writes |

`CandidateFacingStatus` contains `APPLIED`, `PROFILE_VIEWED`, `SHORTLISTED`, `RECRUITER_INTERESTED`, `INTERVIEW_REQUESTED`, `OFFER_MADE`, `NOT_SELECTED`, and `WITHDRAWN`. Submission publishes `APPLIED`. Status preview accepts an `InternalRecruitingStatus` and may suggest the mapped `CandidateFacingStatus`; Sourced, Not relevant, Hired, and other unmapped internal states return null. First view may suggest `PROFILE_VIEWED`; internal Shortlisted may suggest `SHORTLISTED`; Contacted/Screening may suggest `RECRUITER_INTERESTED`; Interviewing may suggest `INTERVIEW_REQUESTED`; Offered may suggest `OFFER_MADE`; Rejected may suggest `NOT_SELECTED`. Publication accepts only an explicitly selected `CandidateFacingStatus`, and every recruiter-originated publication requires preview and confirmation. Candidate-confirmed withdrawal publishes `WITHDRAWN`.

### `application_status_event`

Append-only history containing prior/new internal state, suggested candidate state, published candidate state if explicitly confirmed, actor, reason, idempotency key, source request, and timestamp.

### `recruiter_entered_candidate`

Tenant-scoped synthetic record for the launch organization workflow. Fields: `id`, `tenant_id`, creator, display facts needed by approved search fixtures, immutable `source_type=RECRUITER_ENTERED_SYNTHETIC`, conspicuous source label, search eligibility, version, and timestamps. It MUST contain synthetic data only, MUST NOT contain real contact details or a resume, MUST NOT be exposed outside its tenant, and MUST NOT merge with or overwrite a candidate-controlled profile. Production acceptance of real recruiter-entered people is outside launch scope and requires a separate specification and privacy review.

### `candidate_work_record`

Tenant-owned sourced-candidate aggregate with `tenant_id`, `candidate_profile_id`, required `originating_search_id`, optional `opening_id`, internal status, shortlist state/order, structured reasons, version, actors, and timestamps. Unique active record per `(tenant_id, candidate_profile_id, originating_search_id)`. First authorized view, note, shortlist, or internal status change creates/reuses it. A later application may reference it, but the two aggregates never merge or implicitly copy state.

### `recruiter_note`

Tenant scoped and owned by exactly one `candidate_work_record` or `application` context, with encrypted body, author, optional visibility to an authorized hiring team, `version`, timestamps, and deletion tombstone. Candidate and Tenant Admin cannot read content by role alone. A database check constraint requires exactly one context owner.

### `search_definition`

Tenant and actor scoped with the authoritative `criteria.context`, original prompt, review state, model/prompt version, query hash, created/last-used timestamps, and `version`. `criteria.context.type` is `AD_HOC` or `OPENING`: `AD_HOC` contains no `opening_id`, while `OPENING` contains exactly one `opening_id` that the service verifies is tenant-owned and active at execution time. Only `OPENING` may retrieve `MATCHING_ROLES`; `AD_HOC` retrieves only explicitly authorized `APPROVED_RECRUITERS` profiles. Store only six recent `AD_HOC` searches per user unless explicitly saved; evict least recently used.

If PostgreSQL retains `derived_opening_id` or `derived_context_type` for foreign-key enforcement or indexing, those columns are server-derived and read-only. A database constraint requires derived context to equal `criteria.context`, requires `derived_opening_id IS NULL` for `AD_HOC`, and requires `derived_opening_id = criteria.context.opening_id` for `OPENING`. Client writes never accept either derived field.

### `saved_search`

Tenant- and owner-scoped named reference to one immutable/versioned `search_definition`, with name, saved search version, result-context snapshot reference, and timestamps. It has no independently writable or externally represented `opening_id`; its sole opening context is the referenced search definition's `criteria.context.opening_id`. Any denormalized database opening foreign key is server-derived, read-only, and constrained to equal that value.

### `search_criteria_group` / `search_criterion`

`search_criteria_group` contains `id` (stable UUID), `search_definition_id`, purpose (`REQUIREMENT`, `PREFERENCE`, `EXCLUSION`), operator (`ANY`, `ALL`), display order, label, and `version`. Unique `(search_definition_id, id)` and an operator check prevent ambiguous group identity or semantics.

`search_criterion` contains `id` (stable UUID), `search_definition_id`, required `group_id`, allowlisted field, operator, typed value, display order, provenance, and `version`. A composite foreign key `(search_definition_id, group_id)` requires every criterion to reference exactly one group in the same search. Duplicate IDs, missing groups, and unsupported field/operator/value combinations are rejected before persistence. Requirement groups determine eligibility, preference groups influence ordering only, and exclusion groups are applied deterministically using the group's `ANY` or `ALL` operator.

### `search_result_snapshot`

Short-lived, tenant scoped evidence for reproducibility: search version, candidate id, rank, deterministic score components, evidence ids, authorized visibility snapshot, and expiry. Do not persist generated prose beyond the minimum debugging/evaluation window.

### `shortlist` / `shortlist_member`

Tenant/opening scoped collections with owner/team scope. Membership unique per candidate, includes ordering and timestamps; comparison always re-authorizes every profile at read time.

### `disclosure_request`

Tenant-scoped contact/share aggregate containing candidate, exact application or candidate-work context, purpose, destination type and identifier, requested field scope, current consent/visibility grant, preview hash/expiry, explicit confirmer, delivery/handoff state, idempotency key, and timestamps. Confirmation re-authorizes current consent and object scope and records both the candidate disclosure history and receiving-tenant audit history. The aggregate stores no unnecessary candidate values.

## Communications, Jobs, and Audit

### `notification`

Fields: tenant (nullable for candidate lifecycle), candidate/application, channel, template/version, destination ciphertext, consent basis, internal delivery state (`QUEUED`, `SENDING`, `SENT`, `FAILED`, `CANCELLED`), provider reference, attempts, next attempt, terminal error category, idempotency key, timestamps. Candidate-facing projections expose only `PENDING`, `SENT`, `FAILED`, or `CANCELLED`: both `QUEUED` and `SENDING` map to `PENDING`. Never log body or destination.

### `outbox_event`

Transactionally inserted event: aggregate type/id/version, event type, minimized payload, idempotency key, occurred/published timestamps, attempts. Unique idempotency key prevents double publication.

### `workflow_run`

Tracks async process and optional LangGraph checkpoint: workflow type, actor/tenant/candidate/application scope, status, current step, input hash, model/prompt versions, `expires_at`, and last error category. Checkpoint payload is encrypted and contains only the minimum resumable state.

### `audit_event`

Append-only fields: sequence/id, occurred time, actor identity and effective role, tenant, action, object type/id, decision (`ALLOWED`, `DENIED`, `FAILED`), purpose/reason code, grant/approval reference, request/correlation ids, network risk token, changed-field names, prior/new record versions, result/error category, hash-chain predecessor, and event hash. Do not store candidate field values, resume content, note bodies, tokens, or notification bodies.

Audit-history reads use the same event stream with action `AUDIT_READ` and record query scope, actor, purpose, result count band, and outcome without copying returned event bodies. Tenant Admin access is limited to redacted tenant-administration metadata; candidate-content fields remain unavailable by role alone.

### `access_review`

Periodic review record with tenant or platform scope, review type (`MEMBERSHIP`, `PRIVILEGED_ROLE`, `PURPOSE_GRANT`, `EMERGENCY_GRANT`, `AUDIT_ACCESS`), population snapshot/hash, due and completion times, reviewer independent from reviewed assignments where required, decisions, resulting revocations, exceptions with owner/expiry, and audit references. Reviews never embed candidate content.

### `data_rights_request`, `rights_export`, `active_process_retention_exception`, `legal_hold`, `deletion_ledger`

- `data_rights_request`: access/correction/export/withdraw/hide/delete request, identity verification and step-up evidence where required, submitted/target/completed times, scope, `PENDING|IN_PROGRESS|HELD|COMPLETED|FAILED|CANCELLED`, safe candidate-visible detail, active-process/legal-hold exception, support escalation, and audit references. Access/correction/withdraw/hide are immediate; export target is 24 hours; confirmed deletion target is 30 days.
- `rights_export`: request, encrypted S3 object key, content manifest/hash, generation state, ready time, authenticated download count, 24-hour expiry, deletion time, and failure category. Partial artifacts are never downloadable.
- `active_process_retention_exception`: versioned record with `id`, `version`, `candidate_profile_id`, `application_id`, `policy_version`, `legal_basis`, exact `retained_data_scope`, lifecycle state (`ACTIVE`, `UNDER_REVIEW`, `RESOLVED`, `REVOKED`), `start_date`, mandatory `review_date`, `terminating_event`, nullable `resolution_date`, `approved_by`, and immutable audit references. Candidate and application references are required and tenant-consistent. Resolution or revocation resumes deletion for the covered scope; the record cannot authorize unrelated processing.
- `legal_hold`: exact scope, authority/reference, approver, start/review/end, and encrypted rationale. A hold pauses only covered deletion and remains invisible to ordinary users.
- `deletion_ledger`: non-identifying subject token, deletion scope, source completion statuses, backup cutoff, replay status, and completion evidence. Used to prevent restoring deleted data from backups.

## State Machines

### Resume

```text
UPLOADING -> SCANNING -> PARSING -> REVIEW_REQUIRED -> READY
                 |          |             |
                 v          v             v
             SCAN_FAILED  PARSE_FAILED  REJECTED
                              |
                              v
                     manual profile entry
```

Only `READY` clean objects can be downloaded by an authorized user. `PARSE_FAILED` does not change scan status.

### Candidate lifecycle

```text
DRAFT -> REVIEW_REQUIRED -> PUBLISHED <-> HIDDEN
                              |
                    30-day renewal notice
                              |
          renewed ----------> | <---------- no response
                                             |
                                   DELETION_PENDING -> DELETED
```

Only application or candidate-work states enumerated by the approved versioned retention policy may pause the affected expiry. Each active-process exception records exact retained scope, mandatory review date, and terminating event; candidate-facing status alone never creates or extends an exception. Scoped legal holds remain separate. Withdrawing visibility is immediate and independent of eventual erasure.

### Notification

```text
QUEUED -> SENDING -> SENT
   ^          |
   |          v
 bounded retryable failure
              |
              v
            FAILED -> DLQ/operator reconciliation
```

### Emergency access

```text
REQUESTED -> APPROVED -> ACTIVE -> EXPIRED
     |          |          |
     v          v          v
 REJECTED    REVOKED    REVOKED
```

Every transition is audited. Authorization checks expiry and scope on every request, not only when the session starts.

### Candidate rights request

```text
PENDING -> IN_PROGRESS -> COMPLETED
   |            |             |
   |            v             v
   +---------> HELD ------> IN_PROGRESS
                |
                v
              FAILED -> support escalation / safe retry

PENDING or HELD -> CANCELLED when cancellation remains legally and operationally valid
```

Consent withdrawal/profile hiding changes visibility immediately even while downstream deletion is `IN_PROGRESS` or `HELD`. Export links expire 24 hours after readiness. Confirmed deletion completes within 30 days except for the exact held scope.

## RLS and Authorization Invariants

1. A tenant table is unreadable unless `app.tenant_id` matches the row and an active membership/object grant authorizes the operation.
2. Tenant Admin membership alone never grants recruiter-note, resume, candidate-contact, or application-answer content.
3. Candidate profile access requires ownership, an application/visibility grant for the active tenant and purpose, or an active independently approved emergency grant.
4. Search applies RLS/authorization before ranking, aggregation, pagination, or embedding retrieval.
5. Exports re-authorize each row at execution time and carry a short expiry and download audit.
6. `MATCHING_ROLES` requires deterministic preferences plus an active `OPENING` context;
   `APPROVED_RECRUITERS` requires a non-empty authorized audience; neither schema acceptance nor an
   AI score substitutes for service-layer authorization and eligibility checks.
7. Deletion requires fresh step-up evidence and confirmed consequences, and emergency access
   requires a non-empty `field_scope`; both are revalidated in the service transaction.
6. Background workers set a service identity plus exact tenant/object scope; a missing scope fails closed.
7. Cross-tenant joins are forbidden except through an explicit authorized candidate grant function with an audit event.
8. Business-unit identifiers never replace or broaden tenant predicates.
9. Matching-role authorization is deterministic and precedes ranking; AI output cannot grant eligibility.
10. Emergency access requires a different designated Platform Security Admin approver, exact read scope, live expiry/revocation checks, and affected-Tenant-Admin notification.
11. Employment records and findings require the same candidate visibility, purpose, object, and
    field-scope authorization as their source profile; a finding never broadens access to evidence.

## Indexes and Partitioning

- Unique: verified email HMAC; `(opening_id, candidate_profile_id)` application; active membership; event idempotency keys; active candidate finding by candidate/code/source/calculation version.
- B-tree: tenant plus state/timestamp on openings, applications, notifications, outbox, searches, grants; candidate finding by profile/result/evaluated time.
- GIN: normalized skills/criteria, profile full-text `tsvector`, approved JSONB fields.
- GiST/trigram: normalized names/roles/companies for controlled fuzzy matching.
- HNSW `pgvector`: approved evidence embeddings, with visibility/region/status prefilter strategy verified by query plans.
- Monthly range partitions: `audit_event`, `application_status_event`, and high-volume notification/outbox history. Partition creation and retention are automated.
- Cursor pagination uses stable `(rank_key, id)` rather than offsets.

## Retention Summary

| Data | Default lifecycle |
|---|---|
| Inactive candidate profile | 12 months; renewal request 30 days before expiry; erase/anonymize absent renewal |
| Active applications | Retain while active; after closure follow approved application/legal schedule |
| Resume quarantine | Delete after successful promotion or within 24 hours after terminal failure, absent incident hold |
| Search result snapshots | 7 days |
| LangGraph checkpoints | 7 days after completion; maximum 30 days while awaiting human review |
| Export files | 24 hours, then delete |
| Candidate rights requests | Operational record through completion/support window; candidate content follows its source retention and deletion decision |
| Employment records and candidate findings | Follow the candidate profile and source-record correction/deletion; obsolete findings are superseded immediately and erased with the source except minimized audit evidence |
| Recruiter-entered candidate | Synthetic launch data only; delete on tenant sandbox reset or the approved short synthetic-fixture schedule |
| Disclosure requests | Minimized operational/audit evidence under the approved application and disclosure schedule |
| Access reviews | Approved security-governance schedule; no candidate content |
| Application audit | Security/legal schedule to be approved; immutable and minimized, not a substitute for candidate content |
| Backups | 35 days; deletion ledger reapplied after restore |
| Rate-limit counters | Window plus 24 hours; anomaly evidence follows security schedule |

The final application/audit/legal-hold retention durations require legal approval before real data is enabled.
## Frontend migration additions (approved 2026-10-01)

The FM3 security clarification of 2026-10-01 supersedes the earlier assumption
that public discovery could read Opening directly. Add a separate
`PublicOpeningProjection` and a private source-publication link. The projection
has an independently generated public UUID, title, public description, location
text, work arrangement, employment type, published_at, optional closes_at and
publication/active state. Optional public company, experience and skills are not
copied implicitly. Application URLs derive from the public UUID. Source opening
and tenant identifiers live only in the private link, never the public payload.

The source remains authoritative and its forced tenant RLS is unchanged. The
projection requires forced RLS with a SELECT-only public-reader policy restricted
to currently published, active and non-expired rows. The reader is non-owner,
NOLOGIN and NOBYPASSRLS, with no write privileges or source/link table privileges.
Authorized publication synchronizes transactionally with minimized audit events;
unpublication, closure, expiry and deletion make the projection unavailable.
Source changes invalidate prior publication; failures never commit newly private
state with a stale public projection. Existing source rows are not automatically
published by migration. Restricted-role PostgreSQL tests are mandatory.

Independent-publication clarification (2026-10-01): active and current timestamps
determine PUBLISHED; missing/inactive/expired means UNPUBLISHED, independently of
source OPEN. `PublicOpeningProjection.version` (positive bigint, default 1; migration
0014) captures source revision at confirmed publication/withdrawal, never serialized
anonymously. Decisions advance source version but not its internal state. Preview
GET creates no record: an unlinked source uses a keyed non-reversible public UUID,
persisted in the private link only on confirmation. Existing public UUIDs are retained.
The digest is opaque HMAC, not a readable token exposing internal IDs. No new preview
model or role. Existing PAUSED/CLOSED are the unavailable source states; no ARCHIVED
enum or source expiry field is invented. Projection closes_at remains read-enforced.

Recents reuse SearchDefinition, CriteriaGroup and Criterion with existing tenant/actor ownership, created_at ordering, expires_at and six-entry AD_HOC retention. Order by created_at descending then id descending for deterministic ties. SavedSearch remains the explicit named-save relation and lifecycle; exclude named saves from the unsaved recent collection. Restore criteria from current source rows, not SearchResultSnapshot or SavedSearch.result_context_snapshot. GET restoration does not update timestamps, versions or retention. Executing confirmed criteria uses the existing search creation lifecycle. No last-used column or new history model is required; earlier logical LRU wording is refined to existing execution/creation recency for this amendment. Any discovered schema necessity is a blocker to document before implementation.
