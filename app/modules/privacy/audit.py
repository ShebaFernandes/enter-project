from modules.audit.service import record_audit_event


def audit_rights_action(*, actor, request, action: str, outcome: str = "ALLOWED", metadata=None):
    return record_audit_event(
        actor=actor,
        action=action,
        target_type="data_rights_request",
        target_id=str(request.id),
        outcome=outcome,
        metadata=metadata or {"request_type": request.request_type, "state": request.state},
    )
