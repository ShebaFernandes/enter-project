from datetime import date, timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.utils import timezone

from modules.abuse.policy import create_override
from modules.audit.checkpoints import CheckpointUnavailable, create_daily_checkpoint
from modules.audit.models import AuditEvent
from modules.audit.service import record_event, verify_chain
from modules.communications.models import NotificationDeadLetter
from modules.communications.service import queue_notification
from modules.communications.workers import deliver, redrive
from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import AuthorizationRequest, authorize

pytestmark = pytest.mark.django_db


class MemoryStore:
    def __init__(self, fail=False):
        self.fail = fail
        self.objects = {}

    def sign(self, digest):
        if self.fail:
            raise RuntimeError
        return b"kms-signature"

    def put_locked(self, key, payload):
        if self.fail:
            raise RuntimeError
        self.objects[key] = payload


class FailingAdapter:
    def send(self, **_kwargs):
        raise TimeoutError("synthetic provider timeout")


def test_audit_chain_is_immutable_and_minimized(identity, tenant):
    first = record_event(
        actor=identity,
        tenant_id=tenant.id,
        action="READ",
        target_type="tenant",
        outcome="ALLOWED",
        metadata={"email": "not-logged", "reason_code": "support"},
    )
    second = record_event(
        actor=identity,
        tenant_id=tenant.id,
        action="UPDATE",
        target_type="tenant",
        outcome="ALLOWED",
    )
    assert "email" not in first.metadata
    nested = record_event(
        actor=identity,
        tenant_id=tenant.id,
        action="READ",
        target_type="candidate",
        outcome="ALLOWED",
        metadata={"safe": {"token": "forbidden", "field_names": ["skills"]}},
    )
    assert "token" not in nested.metadata["safe"]
    assert second.previous_hash == first.event_hash
    assert verify_chain()
    with pytest.raises(TypeError):
        first.delete()


def test_checkpoint_is_durable_before_record(identity):
    record_event(actor=identity, action="READ", target_type="tenant", outcome="ALLOWED")
    store = MemoryStore()
    checkpoint = create_daily_checkpoint(date.today(), store)
    assert checkpoint.object_key in store.objects


def test_checkpoint_failure_is_closed(identity):
    record_event(actor=identity, action="READ", target_type="tenant", outcome="ALLOWED")
    with pytest.raises(CheckpointUnavailable):
        create_daily_checkpoint(date.today(), MemoryStore(fail=True))


@pytest.mark.django_db(transaction=True)
def test_database_prevents_audit_update_and_delete(identity):
    event = record_event(actor=identity, action="ADMIN", target_type="tenant", outcome="ALLOWED")
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL immutable trigger required")
    with pytest.raises(DatabaseError), connection.cursor() as cursor:
        cursor.execute("UPDATE audit_auditevent SET action = 'TAMPERED' WHERE id = %s", [event.id])


def test_hash_verification_detects_database_tampering(identity):
    event = record_event(actor=identity, action="READ", target_type="tenant", outcome="ALLOWED")
    if connection.vendor == "postgresql":
        pytest.skip("PostgreSQL trigger prevents constructing a tampered fixture")
    AuditEvent = type(event)
    AuditEvent.objects.filter(pk=event.pk).update(event_hash="0" * 64)
    assert verify_chain() is False


def test_denied_access_override_and_admin_actions_are_audited(identity, tenant):
    with pytest.raises(PermissionDenied):
        authorize(
            AuthorizationRequest(
                action="candidate.read",
                role=TenantMembership.Role.TENANT_ADMIN,
                tenant_id=tenant.id,
                object_tenant_id=tenant.id,
                actor=identity,
                sensitive=True,
            )
        )
    create_override(
        subject_token="-".join(("synthetic", "audit", "subject")),
        action="otp",
        reason_code="VERIFIED_SUPPORT_RECOVERY",
        approved_by=identity,
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    record_event(
        actor=identity,
        tenant_id=tenant.id,
        action="TENANT_ADMIN_SETTINGS_UPDATE",
        target_type="tenant",
        target_id=str(tenant.id),
        outcome="ALLOWED",
    )
    assert AuditEvent.objects.filter(outcome="DENIED", action="candidate.read").exists()
    assert AuditEvent.objects.filter(action="ABUSE_OVERRIDE_CREATE").exists()
    assert AuditEvent.objects.filter(action="TENANT_ADMIN_SETTINGS_UPDATE").exists()


def test_dead_letter_and_redrive_are_audited(identity, tenant):
    notification, _ = queue_notification(
        destination="candidate@synthetic.invalid",
        channel="EMAIL",
        template_key="synthetic-audit",
        template_version="v1",
        consent_basis="SECURITY_REQUIRED",
        idempotency_key="synthetic-audit-dead-letter",
        tenant_id=tenant.id,
    )
    for _ in range(5):
        deliver(notification.id, adapter=FailingAdapter())
    dead_letter = NotificationDeadLetter.objects.get(notification=notification)
    redrive(dead_letter.id, actor=identity)
    assert AuditEvent.objects.filter(action="NOTIFICATION_DEAD_LETTER").exists()
    assert AuditEvent.objects.filter(action="NOTIFICATION_DLQ_REDRIVE").exists()
