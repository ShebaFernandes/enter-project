from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import transaction

from .models import AuditEvent

FORBIDDEN_KEYS = {
    "resume",
    "resume_body",
    "note",
    "note_body",
    "token",
    "email",
    "phone",
    "notification_body",
}


def _minimize(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key.lower() not in FORBIDDEN_KEYS}


@transaction.atomic
def record_event(
    *,
    actor,
    action: str,
    target_type: str,
    outcome: str,
    tenant_id=None,
    target_id: str = "",
    purpose_code: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    previous = AuditEvent.objects.select_for_update().order_by("-occurred_at", "-id").first()
    previous_hash = previous.event_hash if previous else ""
    safe_metadata = _minimize(metadata or {})
    canonical = json.dumps(
        {
            "actor_id": str(getattr(actor, "pk", "")),
            "tenant_id": str(tenant_id or ""),
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "purpose_code": purpose_code,
            "outcome": outcome,
            "metadata": safe_metadata,
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return AuditEvent.objects.create(
        actor=actor,
        tenant_id=tenant_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        purpose_code=purpose_code,
        outcome=outcome,
        metadata=safe_metadata,
        previous_hash=previous_hash,
        event_hash=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def verify_chain() -> bool:
    previous_hash = ""
    for event in AuditEvent.objects.order_by("occurred_at", "id"):
        if event.previous_hash != previous_hash:
            return False
        previous_hash = event.event_hash
    return True


def record_audit_event(*, effective_role: str = "", reason_code: str = "", **kwargs) -> AuditEvent:
    metadata = dict(kwargs.pop("metadata", {}) or {})
    if effective_role:
        metadata["effective_role"] = effective_role
    if reason_code:
        metadata["reason_code"] = reason_code
    return record_event(metadata=metadata, **kwargs)
