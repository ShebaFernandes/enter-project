from collections.abc import Callable

from django.db import transaction
from django.utils import timezone

from .models import OutboxEvent, ProcessedEvent

Publisher = Callable[[dict[str, object]], None]


def publish_batch(publisher: Publisher, limit: int = 100) -> int:
    sent = 0
    with transaction.atomic():
        events = list(
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(published_at__isnull=True)
            .order_by("occurred_at")[:limit]
        )
        for event in events:
            publisher(
                {
                    "event_id": str(event.id),
                    "event_type": event.event_type,
                    "occurred_at": event.occurred_at.isoformat(),
                    "aggregate": {
                        "type": event.aggregate_type,
                        "id": str(event.aggregate_id),
                        "version": event.aggregate_version,
                    },
                    "tenant_id": str(event.tenant_id) if event.tenant_id else None,
                    "actor_id": str(event.actor_id) if event.actor_id else None,
                    "correlation_id": str(event.correlation_id) if event.correlation_id else None,
                    "payload": event.payload,
                    "idempotency_key": event.idempotency_key,
                }
            )
            event.published_at = timezone.now()
            event.attempts += 1
            event.save(update_fields=["published_at", "attempts"])
            sent += 1
    return sent


def claim_once(event_id: object, consumer: str) -> bool:
    _, created = ProcessedEvent.objects.get_or_create(event_id=event_id, consumer=consumer)
    return created
