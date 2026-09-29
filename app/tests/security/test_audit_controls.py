from datetime import date

import pytest

from modules.audit.checkpoints import CheckpointUnavailable, create_daily_checkpoint
from modules.audit.service import record_event, verify_chain

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
