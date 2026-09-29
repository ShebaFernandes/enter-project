from __future__ import annotations

from django.db import transaction

from modules.operations.crypto import encrypt
from modules.operations.outbox import enqueue

from .models import Notification


@transaction.atomic
def queue_notification(
    *,
    destination: str,
    channel: str,
    template_key: str,
    template_version: str,
    consent_basis: str,
    idempotency_key: str,
    tenant_id=None,
    candidate_profile_id=None,
    application_id=None,
) -> tuple[Notification, bool]:
    existing = Notification.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False
    notification = Notification.objects.create(
        tenant_id=tenant_id,
        candidate_profile_id=candidate_profile_id,
        application_id=application_id,
        channel=channel,
        template_key=template_key,
        template_version=template_version,
        destination_ciphertext=encrypt(destination),
        consent_basis=consent_basis,
        idempotency_key=idempotency_key,
    )
    enqueue(
        aggregate_type="notification",
        aggregate_id=notification.id,
        aggregate_version=1,
        event_type="notification.queued.v1",
        payload={"notification_id": str(notification.id), "channel": channel},
        idempotency_key=f"notification-event:{idempotency_key}",
        tenant_id=tenant_id,
    )
    return notification, True


def candidate_projection(notification: Notification) -> dict[str, object]:
    return {
        "id": str(notification.id),
        "channel": notification.channel,
        "state": notification.candidate_state,
        "safe_error": notification.terminal_error_category or None,
    }
