from modules.audit.service import record_audit_event


def audit_search(*, actor, tenant_id, search_id, outcome, result_count=0):
    return record_audit_event(
        actor=actor,
        tenant_id=tenant_id,
        action="CANDIDATE_SEARCH",
        target_type="search",
        target_id=str(search_id),
        purpose_code="RECRUITING_DISCOVERY",
        outcome=outcome,
        metadata={"result_count": result_count},
    )


def audit_search_denial(*, actor, tenant_id, reason_code):
    return record_audit_event(
        actor=actor,
        tenant_id=tenant_id,
        action="CANDIDATE_SEARCH",
        target_type="tenant",
        target_id=str(tenant_id),
        purpose_code="RECRUITING_DISCOVERY",
        outcome="DENIED",
        metadata={"reason_code": reason_code},
    )


def audit_result_view(*, actor, tenant_id, search_id, candidate_id, outcome):
    return record_audit_event(
        actor=actor,
        tenant_id=tenant_id,
        action="SEARCH_RESULT_VIEW",
        target_type="candidate_profile",
        target_id=str(candidate_id),
        purpose_code="RECRUITING_DISCOVERY",
        outcome=outcome,
        metadata={"search_id": str(search_id)},
    )
