import uuid

import pytest

from modules.operations.outbox import enqueue
from modules.operations.workers import claim_once, publish_batch

pytestmark = pytest.mark.django_db


def test_minimized_versioned_event_envelope_is_published():
    event_id = uuid.uuid4()
    enqueue(
        aggregate_type="tenant",
        aggregate_id=event_id,
        aggregate_version=1,
        event_type="tenant.provisioned.v1",
        payload={"changed_fields": ["status"]},
        idempotency_key=f"tenant:{event_id}:1",
        tenant_id=event_id,
    )
    published: list[dict[str, object]] = []
    assert publish_batch(published.append) == 1
    envelope = published[0]
    assert set(envelope) == {
        "event_id",
        "event_type",
        "occurred_at",
        "aggregate",
        "tenant_id",
        "actor_id",
        "correlation_id",
        "payload",
        "idempotency_key",
    }
    assert envelope["event_type"].endswith(".v1")


def test_sensitive_event_payload_is_rejected():
    with pytest.raises(ValueError):
        enqueue(
            aggregate_type="tenant",
            aggregate_id=uuid.uuid4(),
            aggregate_version=1,
            event_type="tenant.updated.v1",
            payload={"note_text": "must not leave source aggregate"},
            idempotency_key="sensitive",
        )


def test_processed_event_marker_is_per_consumer():
    event_id = uuid.uuid4()
    assert claim_once(event_id, "consumer-a")
    assert not claim_once(event_id, "consumer-a")
    assert claim_once(event_id, "consumer-b")
