from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction

from modules.operations.concurrency import require_match

from .audit import record_recruiting_event
from .candidate_work import authorize_application, authorize_candidate_work
from .work_models import RecruiterNote


def _authorize_note(membership, note: RecruiterNote, action: str) -> None:
    if note.candidate_work_id:
        if note.candidate_work is None:
            raise PermissionDenied("Note unavailable")
        authorize_candidate_work(membership, note.candidate_work, action)
    else:
        if note.application is None:
            raise PermissionDenied("Note unavailable")
        authorize_application(membership, note.application, action)
    if membership.role == "HIRING_MANAGER" and not note.hiring_team_visible:
        raise PermissionDenied("Note unavailable")


def note_data(note: RecruiterNote) -> dict[str, object]:
    return {
        "id": str(note.id),
        "context_type": "CANDIDATE_WORK" if note.candidate_work_id else "APPLICATION",
        "context_id": str(note.candidate_work_id or note.application_id),
        "author_id": str(note.author_id),
        "body": note.body,
        "version": note.version,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def list_notes(*, membership, candidate_work=None, application=None):
    if (candidate_work is None) == (application is None):
        raise ValueError("Exactly one note context is required.")
    if candidate_work is not None:
        authorize_candidate_work(membership, candidate_work, "recruiter_note.read")
        queryset = RecruiterNote.objects.filter(candidate_work=candidate_work)
    else:
        authorize_application(membership, application, "recruiter_note.read")
        queryset = RecruiterNote.objects.filter(application=application)
    if membership.role == "HIRING_MANAGER":
        queryset = queryset.filter(hiring_team_visible=True)
    return queryset.filter(deleted_at__isnull=True).select_related("author").order_by("created_at")


@transaction.atomic
def create_note(
    *, membership, body: str, candidate_work=None, application=None, hiring_team_visible=False
) -> RecruiterNote:
    if (candidate_work is None) == (application is None):
        raise ValueError("Exactly one note context is required.")
    if membership.role == "HIRING_MANAGER" and not hiring_team_visible:
        raise PermissionDenied("Note unavailable")
    if candidate_work is not None:
        authorize_candidate_work(membership, candidate_work, "recruiter_note.write")
        tenant_id = candidate_work.tenant_id
    else:
        authorize_application(membership, application, "recruiter_note.write")
        tenant_id = application.tenant_id
    note = RecruiterNote(
        tenant_id=tenant_id,
        candidate_work=candidate_work,
        application=application,
        author=membership.identity,
        hiring_team_visible=hiring_team_visible,
    )
    note.set_body(body)
    note.full_clean()
    note.save()
    record_recruiting_event(
        actor=membership.identity,
        tenant_id=tenant_id,
        action="RECRUITER_NOTE_CREATED",
        target_type="recruiter_note",
        target_id=note.id,
        context_type="CANDIDATE_WORK" if candidate_work is not None else "APPLICATION",
        context_id=str(candidate_work.id if candidate_work is not None else application.id),
        changed_fields=["body"],
        version=note.version,
    )
    return note


@transaction.atomic
def update_note(*, membership, note_id, body: str, if_match: str | None) -> RecruiterNote:
    note = RecruiterNote.objects.select_for_update().get(
        pk=note_id, tenant_id=membership.tenant_id, deleted_at__isnull=True
    )
    _authorize_note(membership, note, "recruiter_note.write")
    attempted: dict[str, object] = {"body": body}
    require_match(
        if_match,
        object_id=note.id,
        version=note.version,
        current={"body": note.body},
        attempted=attempted,
    )
    note.set_body(body)
    note.version += 1
    note.full_clean()
    note.save(update_fields=("body_ciphertext", "version", "updated_at"))
    record_recruiting_event(
        actor=membership.identity,
        tenant_id=note.tenant_id,
        action="RECRUITER_NOTE_UPDATED",
        target_type="recruiter_note",
        target_id=note.id,
        changed_fields=["body"],
        version=note.version,
    )
    return note
