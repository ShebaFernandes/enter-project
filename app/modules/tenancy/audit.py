from modules.audit.service import record_audit_event


def record_governance_event(
    *,
    membership,
    action: str,
    target_type: str,
    target_id: object,
    outcome: str = "ALLOWED",
    **metadata,
):
    return record_audit_event(
        actor=membership.identity,
        effective_role=membership.role,
        tenant_id=membership.tenant_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        outcome=outcome,
        metadata=metadata,
    )
