import pytest
from django.core.exceptions import PermissionDenied

from modules.audit.models import AuditEvent
from modules.operations.concurrency import StaleWrite, strong_etag
from modules.recruiting.notes import create_note, update_note
from tests.factories import ApplicationFactory, MembershipFactory, TenantFactory


@pytest.mark.django_db
def test_note_has_exactly_one_context_and_audit_redacts_body(recruiter):
    application = ApplicationFactory(tenant=recruiter.tenant, opening__tenant=recruiter.tenant)
    note = create_note(
        membership=recruiter,
        application=application,
        body="Synthetic private assessment",
    )
    assert note.application_id == application.id
    assert note.candidate_work_id is None
    audit = AuditEvent.objects.get(action="RECRUITER_NOTE_CREATED")
    assert "Synthetic private assessment" not in str(audit.metadata)


@pytest.mark.django_db
def test_note_tenant_isolation_and_stale_reconciliation(recruiter):
    application = ApplicationFactory(tenant=recruiter.tenant, opening__tenant=recruiter.tenant)
    note = create_note(membership=recruiter, application=application, body="Original")
    other_tenant = TenantFactory()
    outsider = MembershipFactory(tenant=other_tenant)
    with pytest.raises((PermissionDenied, type(note).DoesNotExist)):
        update_note(
            membership=outsider,
            note_id=note.id,
            body="Cross tenant",
            if_match=strong_etag(note.id, note.version),
        )
    updated = update_note(
        membership=recruiter,
        note_id=note.id,
        body="Current",
        if_match=strong_etag(note.id, note.version),
    )
    with pytest.raises(StaleWrite) as conflict:
        update_note(
            membership=recruiter,
            note_id=note.id,
            body="Attempted stale edit",
            if_match=strong_etag(note.id, 1),
        )
    assert conflict.value.reconciliation["current"]["body"] == "Current"
    assert conflict.value.reconciliation["attempted"]["body"] == "Attempted stale edit"
    assert updated.body == "Current"
