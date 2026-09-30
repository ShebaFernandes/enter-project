from __future__ import annotations

from django.db import transaction

from modules.operations.concurrency import require_match

from .application_models import Application, InternalRecruitingStatus
from .applications import preview_candidate_status, publish_candidate_status
from .audit import record_recruiting_event
from .candidate_work import authorize_application, authorize_candidate_work
from .statuses import candidate_status_suggestion, validate_not_relevant
from .work_models import CandidateWorkRecord, RecruitingStatusEvent, ShortlistEntry

__all__ = ["preview_candidate_status", "publish_candidate_status"]


def _set_shortlist(*, owner, membership, selected: bool) -> None:
    if isinstance(owner, CandidateWorkRecord):
        queryset = ShortlistEntry.objects.filter(candidate_work=owner)
        if selected:
            ShortlistEntry.objects.update_or_create(
                candidate_work=owner,
                defaults={
                    "tenant_id": owner.tenant_id,
                    "selected": True,
                    "selected_by": membership.identity,
                },
            )
    else:
        queryset = ShortlistEntry.objects.filter(application=owner)
        if selected:
            ShortlistEntry.objects.update_or_create(
                application=owner,
                defaults={
                    "tenant_id": owner.tenant_id,
                    "selected": True,
                    "selected_by": membership.identity,
                },
            )
    if not selected:
        queryset.update(selected=False, version=models.F("version") + 1)


@transaction.atomic
def update_candidate_work(
    *,
    membership,
    record: CandidateWorkRecord,
    if_match: str | None,
    request_key: str,
    internal_status: str | None = None,
    shortlisted: bool | None = None,
    structured_reasons: list[str] | None = None,
    explanatory_note: str | None = None,
) -> CandidateWorkRecord:
    record = CandidateWorkRecord.objects.select_for_update().get(
        pk=record.pk, tenant_id=membership.tenant_id
    )
    authorize_candidate_work(membership, record, "candidate_work.write")
    attempted: dict[str, object] = {
        key: value
        for key, value in {
            "internal_status": internal_status,
            "shortlisted": shortlisted,
            "structured_reasons": structured_reasons,
            "explanatory_note": explanatory_note,
        }.items()
        if value is not None
    }
    require_match(
        if_match,
        object_id=record.id,
        version=record.version,
        current={
            "internal_status": record.internal_status,
            "shortlisted": record.shortlisted,
            "structured_reasons": record.structured_reasons,
            "explanatory_note": record.explanatory_note,
        },
        attempted=attempted,
    )
    prior = record.internal_status
    next_status = internal_status or record.internal_status
    reasons = structured_reasons if structured_reasons is not None else record.structured_reasons
    note = explanatory_note if explanatory_note is not None else record.explanatory_note
    validate_not_relevant(
        internal_status=next_status, structured_reasons=reasons, explanatory_note=note
    )
    record.internal_status = next_status
    record.structured_reasons = [value.strip() for value in reasons if value.strip()]
    if explanatory_note is not None:
        record.set_explanatory_note(explanatory_note)
    if shortlisted is not None:
        record.shortlisted = shortlisted
        _set_shortlist(owner=record, membership=membership, selected=shortlisted)
    elif next_status == InternalRecruitingStatus.SHORTLISTED:
        record.shortlisted = True
        _set_shortlist(owner=record, membership=membership, selected=True)
    record.updated_by = membership.identity
    record.version += 1
    record.full_clean()
    record.save()
    if prior != next_status:
        RecruitingStatusEvent.objects.create(
            tenant_id=record.tenant_id,
            candidate_work=record,
            prior_status=prior,
            new_status=next_status,
            structured_reasons=record.structured_reasons,
            actor=membership.identity,
            idempotency_key=f"candidate-work-status:{request_key}",
        )
    record_recruiting_event(
        actor=membership.identity,
        tenant_id=record.tenant_id,
        action="CANDIDATE_WORK_UPDATED",
        target_type="candidate_work",
        target_id=record.id,
        changed_fields=sorted(attempted),
        version=record.version,
    )
    return record


@transaction.atomic
def update_application_internal_status(
    *,
    membership,
    application_id,
    internal_status: str,
    structured_reasons: list[str],
    explanatory_note: str | None,
    if_match: str | None,
    request_key: str,
) -> Application:
    application = (
        Application.objects.select_for_update()
        .select_related("opening")
        .get(pk=application_id, tenant_id=membership.tenant_id)
    )
    authorize_application(membership, application, "application.status.write")
    validate_not_relevant(
        internal_status=internal_status,
        structured_reasons=structured_reasons,
        explanatory_note=explanatory_note,
    )
    attempted: dict[str, object] = {
        "internal_status": internal_status,
        "structured_reasons": structured_reasons,
        "explanatory_note": explanatory_note,
    }
    require_match(
        if_match,
        object_id=application.id,
        version=application.version,
        current={"internal_status": application.internal_status},
        attempted=attempted,
    )
    prior = application.internal_status
    application.internal_status = internal_status
    application.suggested_candidate_status = candidate_status_suggestion(internal_status)
    application.version += 1
    application.save(
        update_fields=("internal_status", "suggested_candidate_status", "version", "updated_at")
    )
    RecruitingStatusEvent.objects.create(
        tenant_id=application.tenant_id,
        application=application,
        prior_status=prior,
        new_status=internal_status,
        structured_reasons=[value.strip() for value in structured_reasons if value.strip()],
        actor=membership.identity,
        idempotency_key=f"application-internal-status:{request_key}",
    )
    _set_shortlist(
        owner=application,
        membership=membership,
        selected=internal_status == InternalRecruitingStatus.SHORTLISTED,
    )
    record_recruiting_event(
        actor=membership.identity,
        tenant_id=application.tenant_id,
        action="APPLICATION_INTERNAL_STATUS_UPDATED",
        target_type="application",
        target_id=application.id,
        changed_fields=["internal_status", "structured_reasons"],
        version=application.version,
    )
    return application


from django.db import models  # noqa: E402
