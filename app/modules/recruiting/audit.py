from __future__ import annotations

from modules.audit.service import record_audit_event


def record_recruiting_event(
    *, actor, tenant_id, action: str, target_type: str, target_id, outcome="ALLOWED", **metadata
):
    """Record identifiers and changed-field names only; never note/contact values."""
    return record_audit_event(
        actor=actor,
        tenant_id=tenant_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        outcome=outcome,
        purpose_code="RECRUITING_MANAGEMENT",
        metadata=metadata,
    )


def record_disclosure_histories(*, actor, disclosure, outcome: str, result_category: str = ""):
    common = {
        "context_type": "APPLICATION" if disclosure.application_id else "CANDIDATE_WORK",
        "context_id": str(disclosure.application_id or disclosure.candidate_work_id),
        "permitted_fields": sorted(disclosure.permitted_fields),
        "result_category": result_category,
    }
    candidate_event = record_audit_event(
        actor=actor,
        tenant_id=None,
        action="CANDIDATE_DISCLOSURE_HISTORY",
        target_type="candidate_profile",
        target_id=str(disclosure.candidate_profile_id),
        outcome=outcome,
        purpose_code=disclosure.purpose,
        metadata={**common, "disclosure_id": str(disclosure.id)},
    )
    tenant_event = record_audit_event(
        actor=actor,
        tenant_id=disclosure.tenant_id,
        action="TENANT_CANDIDATE_DISCLOSURE",
        target_type="disclosure_request",
        target_id=str(disclosure.id),
        outcome=outcome,
        purpose_code=disclosure.purpose,
        metadata={**common, "candidate_audit_id": str(candidate_event.id)},
    )
    return candidate_event, tenant_event
