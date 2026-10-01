# Asynchronous Event Contract

All events use JSON, UTF-8, schema versioning, UUIDv7 event IDs, UTC RFC 3339 timestamps, and an idempotency key. Payloads contain identifiers and changed-field names, never resume content, note text, full prompts, contact details, or authentication tokens.

## Envelope

FM3 independent opening publication uses synchronous minimized governance audit,
not a new asynchronous public-payload event. `OPENING_PUBLISHED` and
`OPENING_PUBLICATION_WITHDRAWN` record existing actor/role/tenant, opening target,
outcome and changed-field names only. Never include titles, descriptions, location
values, preview digests, contact data or candidate information. Explicit decisions
and audit commit atomically; idempotent replay emits no duplicate audit. Source edits
that invalidate a live projection record withdrawal plus existing OPENING_UPDATE.
Direct database invalidation remains a safety backstop, not an alternative management API.

```json
{
  "event_id": "0199...",
  "event_type": "application.candidate_status_publish_requested.v1",
  "occurred_at": "2026-09-28T10:30:00Z",
  "aggregate": {"type": "application", "id": "0199...", "version": 8},
  "tenant_id": "0199...",
  "actor_id": "0199...",
  "correlation_id": "0199...",
  "idempotency_key": "status-publish:0199...:8",
  "payload": {"candidate_status": "INTERVIEW_REQUESTED", "notification_id": "0199..."}
}
```

Consumers reject unknown major schema versions, tolerate additive fields, re-authorize current object state before sensitive effects, and record a processed-event idempotency marker in the same transaction as their state change.

## FM4 transitional handoff audit

Pagination continuation and recent/saved reopening reuse the minimized handoff
creation event. No page token, source criteria, recent prompt or selected candidate
identifier is added to the event payload. Pagination does not emit search execution
events because it only reads existing persisted ordered references.

`SEARCH_HANDOFF_CREATED`, `SEARCH_HANDOFF_RESTORED`, `SEARCH_HANDOFF_REVISED`,
`SEARCH_HANDOFF_REVOKED`, `SEARCH_HANDOFF_COMPLETED` use the existing immutable audit
service. Allow only actor, tenant, effective role, outcome, hashed handoff resource
reference, handoff type and `15_MINUTES` expiry bucket. Never include token, prompt,
criteria, candidate rows or encrypted payload. No new asynchronous consumer or
generic session event is authorized. Denied requests must not reveal token existence.

The approved `comparison-selection` extension uses the same minimized event names
and distinct handoff type. Ordered candidate IDs, arbitrary/full URLs and comparison
return tokens must never enter audit metadata. Final comparison retains its existing
request-time authorization and audit behavior.

## Event Catalog

| Event | Producer | Consumer/effect | Failure rule |
|---|---|---|---|
| `resume.upload_completed.v1` | Upload callback/reconciler | Start malware scan tracking | Fail closed; object stays quarantined |
| `resume.scan_clean.v1` | GuardDuty event adapter | Enqueue sandbox parsing | Verify tag and object hash before use |
| `resume.scan_failed.v1` | GuardDuty event adapter | Mark rejected and notify candidate | Never create download URL |
| `resume.parse_requested.v1` | Resume service | Parser worker | Bounded retry; manual entry remains available |
| `resume.extraction_ready.v1` | Parser worker | Create reviewable suggestions | Never auto-publish fields |
| `profile.published.v1` | Candidate service | Create/update authorized search projection | If indexing fails, mark `INDEX_PENDING` and retry |
| `profile.visibility_changed.v1` | Consent service | Remove/update projections and caches | Privacy-priority queue; alarm on age |
| `profile.employment_history_changed.v1` | Candidate profile service | Recalculate generic findings for changed employment-record IDs and invalidate affected authorized projections | Payload contains IDs/versions and changed-field names only; idempotent by profile/version; never carries company, dates, or departure reason |
| `candidate.findings_recalculated.v1` | Deterministic finding evaluator | Refresh authorized search/detail projections and retire obsolete finding references | Eligibility, score, rank, recommendation, application status, and outcome remain unchanged; re-authorize before projection |
| `profile.deletion_requested.v1` | Rights/lifecycle service | Orchestrate erasure across stores | Durable saga with per-store completion ledger |
| `rights.export_requested.v1` | Rights service | Re-authorize and build complete encrypted export | Complete within 24h; partial artifact never downloadable; link expires 24h after ready |
| `rights.deletion_confirmed.v1` | Rights service | Hide immediately and orchestrate 30-day erasure | Step-up proof required; exact active-process/legal-hold scope may be held |
| `rights.active_process_exception_changed.v1` | Rights service | Schedule review or resume deletion for the exact retained scope | Carry only exception ID/version; re-read the versioned `ActiveProcessRetentionException` and audit authorization before effect |
| `consent.renewal_due.v1` | Lifecycle scheduler | Queue renewal notification | Idempotent per consent cycle |
| `candidate_work.created.v1` | Recruiting service | Record sourced-candidate context for view/note/shortlist/status | Unique per tenant/candidate/originating search; never create an application |
| `candidate_disclosure.confirmed.v1` | Recruiting service | Re-authorize consent/object/field scope and perform the approved contact/share handoff | Abort on changed consent/scope; write candidate disclosure and tenant audit histories; never include disclosed values in the event |
| `application.submitted.v1` | Application service | Notify authorized team/candidate | Application commit is not rolled back by notification failure |
| `application.candidate_status_publish_requested.v1` | Status service | Send explicitly confirmed update | Five attempts/24h then DLQ and visible `FAILED` |
| `embedding.requested.v1` | Search projection service | In-region Bedrock embedding worker | Exact/filter search remains available |
| `export.requested.v1` | Export service | Re-authorize rows and create expiring file | Abort whole export on any auth/storage failure |
| `audit.checkpoint_due.v1` | EventBridge Scheduler | Hash/sign partition checkpoint into Object Lock | Security alarm; never discard source events |
| `access_review.due.v1` | Access-review scheduler | Snapshot review population and notify assigned reviewer | No candidate content; overdue reviews escalate and never silently renew access |
| `recovery.privacy_replay_requested.v1` | Recovery controller | Reapply deletion, withdrawal, tenant revocation, and emergency-grant revocation through the recovery point | Restored data remains inaccessible until verification completes |

## Delivery and Reconciliation

- PostgreSQL outbox polling publishes to SQS only after the business transaction commits.
- SQS visibility timeout exceeds worker timeout; heartbeats extend it only for known bounded work.
- Each queue has a DLQ, age/depth alarms, and a runbook. Redrive is an explicit authorized operation with a reason and audit event.
- Notifications use internal delivery states `QUEUED`, `SENDING`, `SENT`, `FAILED`, and `CANCELLED` and retry no more than five times over 24 hours. Candidate-facing projections map `QUEUED` and `SENDING` to `PENDING` and expose only `PENDING`, `SENT`, `FAILED`, or `CANCELLED`.
- Candidate-status publication event payloads accept only the eight-value `CandidateFacingStatus`; preview inputs use `InternalRecruitingStatus`, may yield a null suggestion for an unmapped state, and emit no publication event. Recruiter-originated publication events require an explicitly selected valid candidate-facing value and explicit preview confirmation.
- EventBridge and S3 notifications are treated as at-least-once; periodic reconciliation finds missing or duplicated transitions.
- Event payload retention follows operational need; source records and audit events remain authoritative.
