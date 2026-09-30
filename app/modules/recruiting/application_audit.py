from __future__ import annotations

from modules.audit.service import record_audit_event


def record_application_event(
    *, actor, application, action: str, outcome: str = "ALLOWED", changed_fields=()
):
    """Record identifiers and changed field names, never answers or contact values."""
    return record_audit_event(
        actor=actor,
        tenant_id=application.tenant_id,
        action=action,
        target_type="application",
        target_id=str(application.id),
        outcome=outcome,
        purpose_code="APPLICATION_PROCESSING",
        metadata={
            "opening_id": str(application.opening_id),
            "changed_fields": sorted(changed_fields),
            "version": application.version,
        },
    )
