from uuid import UUID

from django.db import transaction

from .models import OutboxEvent

FORBIDDEN_PAYLOAD_KEYS = {
    "resume",
    "resume_content",
    "note",
    "note_text",
    "prompt",
    "email",
    "phone",
    "token",
}


def _assert_minimized(value):
    if isinstance(value, dict):
        if FORBIDDEN_PAYLOAD_KEYS & {str(key).lower() for key in value}:
            raise ValueError("Event payload contains prohibited sensitive content")
        for item in value.values():
            _assert_minimized(item)
    elif isinstance(value, list):
        for item in value:
            _assert_minimized(item)


@transaction.atomic
def enqueue(
    *,
    aggregate_type: str,
    aggregate_id: UUID,
    aggregate_version: int,
    event_type: str,
    payload: dict[str, object],
    idempotency_key: str,
    tenant_id=None,
    actor_id=None,
    correlation_id=None,
) -> OutboxEvent:
    _assert_minimized(payload)
    return OutboxEvent.objects.create(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
        tenant_id=tenant_id,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
