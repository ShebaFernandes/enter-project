import hashlib
import hmac
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.communications.adapters import SesAdapter, WhatsAppAdapter, verify_callback_signature
from modules.communications.models import Notification, NotificationDeadLetter
from modules.communications.service import candidate_projection, queue_notification
from modules.communications.workers import MAX_ATTEMPTS, deliver, redrive

pytestmark = pytest.mark.django_db


class FailingAdapter:
    def send(self, **_kwargs):
        raise TimeoutError("synthetic provider timeout")


class SuccessfulAdapter:
    def send(self, **_kwargs):
        return "synthetic-provider-reference"


class FakeSesClient:
    def __init__(self):
        self.call = None

    def send_templated_email(self, **kwargs):
        self.call = kwargs
        return {"MessageId": "synthetic-ses-id"}


def _queue(tenant, suffix="one"):
    return queue_notification(
        destination="candidate@synthetic.invalid",
        channel=Notification.Channel.EMAIL,
        template_key="synthetic-foundation",
        template_version="v1",
        consent_basis="SECURITY_REQUIRED",
        idempotency_key=f"notification-{suffix}",
        tenant_id=tenant.id,
    )


def test_queue_is_idempotent_and_candidate_projection_hides_internal_states(tenant):
    first, created = _queue(tenant)
    replay, replay_created = _queue(tenant)
    assert created is True and replay_created is False
    assert replay.id == first.id
    assert candidate_projection(first)["state"] == "PENDING"
    first.state = Notification.State.SENDING
    assert candidate_projection(first)["state"] == "PENDING"
    first.state = Notification.State.SENT
    assert candidate_projection(first)["state"] == "SENT"
    first.state = Notification.State.FAILED
    assert candidate_projection(first)["state"] == "FAILED"
    first.state = Notification.State.CANCELLED
    assert candidate_projection(first)["state"] == "CANCELLED"
    assert "attempts" not in candidate_projection(first)


def test_signed_callback_validation():
    payload = b'{"status":"delivered"}'
    secret = b"synthetic-callback-secret"
    signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    assert verify_callback_signature(payload=payload, signature=signature, secret=secret)
    assert not verify_callback_signature(payload=payload, signature="0" * 64, secret=secret)


def test_ses_adapter_uses_versioned_template_and_destination():
    client = FakeSesClient()
    reference = SesAdapter(client=client, source="no-reply@synthetic.invalid").send(
        destination="candidate@synthetic.invalid",
        template_key="synthetic-foundation",
        template_version="v1",
    )
    assert reference == "synthetic-ses-id"
    assert client.call == {
        "Source": "no-reply@synthetic.invalid",
        "Destination": {"ToAddresses": ["candidate@synthetic.invalid"]},
        "Template": "synthetic-foundation",
        "TemplateData": '{"version":"v1"}',
    }


def test_delivery_is_bounded_dead_lettered_and_audited_on_redrive(tenant, identity):
    notification, _ = _queue(tenant, "failure")
    for attempt in range(MAX_ATTEMPTS):
        deliver(notification.id, adapter=FailingAdapter())
        notification.refresh_from_db()
        assert notification.attempts == attempt + 1
    assert notification.state == Notification.State.FAILED
    dead_letter = NotificationDeadLetter.objects.get(notification=notification)
    restored = redrive(dead_letter.id, actor=identity)
    assert restored.state == Notification.State.QUEUED
    assert restored.attempts == 0
    assert AuditEvent.objects.filter(action="NOTIFICATION_DLQ_REDRIVE").exists()


def test_delivery_window_expires_after_24_hours_without_another_attempt(tenant):
    notification, _ = _queue(tenant, "expired-window")
    Notification.objects.filter(pk=notification.pk).update(
        created_at=timezone.now() - timedelta(hours=24, seconds=1)
    )
    deliver(notification.id, adapter=SuccessfulAdapter())
    notification.refresh_from_db()
    assert notification.state == Notification.State.FAILED
    assert notification.attempts == 0
    assert notification.terminal_error_category == "DELIVERY_WINDOW_EXHAUSTED"
    assert NotificationDeadLetter.objects.filter(notification=notification).exists()


def test_successful_delivery_is_duplicate_safe(tenant):
    notification, _ = _queue(tenant, "success")
    deliver(notification.id, adapter=SuccessfulAdapter())
    notification.refresh_from_db()
    assert notification.state == Notification.State.SENT
    assert notification.provider_reference == "synthetic-provider-reference"
    deliver(notification.id, adapter=FailingAdapter())
    notification.refresh_from_db()
    assert notification.state == Notification.State.SENT
    assert notification.attempts == 1


def test_whatsapp_is_disabled_until_approved():
    with pytest.raises(RuntimeError, match="WHATSAPP_NOT_APPROVED"):
        WhatsAppAdapter().send(
            destination="synthetic",
            template_key="synthetic",
            template_version="v1",
        )
