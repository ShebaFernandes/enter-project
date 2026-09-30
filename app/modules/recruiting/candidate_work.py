from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from modules.search.eligibility import eligible_profiles
from modules.search.models import SearchDefinition, SearchResultSnapshot
from modules.tenancy.policy import AuthorizationRequest, authorize, authorize_opening

from .application_models import Application
from .audit import record_recruiting_event
from .work_models import CandidateWorkRecord


def _authorize_membership(membership, *, action: str, tenant_id, object_id=None) -> None:
    authorize(
        AuthorizationRequest(
            action=action,
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=tenant_id,
            object_id=str(object_id or ""),
            actor=membership.identity,
        )
    )


def authorize_candidate_work(membership, record: CandidateWorkRecord, action: str) -> None:
    _authorize_membership(
        membership, action=action, tenant_id=record.tenant_id, object_id=record.id
    )
    if record.opening_id:
        authorize_opening(membership, record.opening, "opening.read")
    elif record.originating_search.actor_id != membership.identity_id:
        raise PermissionDenied("Candidate work unavailable")


def authorize_application(membership, application: Application, action: str) -> None:
    _authorize_membership(
        membership, action=action, tenant_id=application.tenant_id, object_id=application.id
    )
    authorize_opening(membership, application.opening, "opening.read")


def candidate_work_data(record: CandidateWorkRecord) -> dict[str, object]:
    return {
        "id": str(record.id),
        "candidate_id": str(record.candidate_profile_id),
        "originating_search_id": str(record.originating_search_id),
        "opening_id": str(record.opening_id) if record.opening_id else None,
        "internal_status": record.internal_status,
        "shortlisted": record.shortlisted,
        "structured_reasons": record.structured_reasons,
        "explanatory_note": record.explanatory_note,
        "version": record.version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _validate_source_access(*, membership, search: SearchDefinition, candidate_id) -> None:
    if search.tenant_id != membership.tenant_id:
        raise PermissionDenied("Candidate work unavailable")
    if search.actor_id != membership.identity_id:
        raise PermissionDenied("Candidate work unavailable")
    if not SearchResultSnapshot.objects.filter(
        search=search, candidate_profile_id=candidate_id
    ).exists():
        raise PermissionDenied("Candidate work unavailable")
    if not eligible_profiles(membership, search.criteria_context).filter(pk=candidate_id).exists():
        raise PermissionDenied("Candidate work unavailable")


@transaction.atomic
def create_or_reuse_candidate_work(
    *, membership, candidate_id, originating_search_id, opening_id=None, trigger: str
) -> tuple[CandidateWorkRecord, bool]:
    if trigger not in {"VIEW", "NOTE", "SHORTLIST", "STATUS_CHANGE"}:
        raise ValidationError({"trigger": "Unsupported candidate-work trigger."})
    search = (
        SearchDefinition.objects.select_related("derived_opening")
        .filter(pk=originating_search_id, tenant_id=membership.tenant_id)
        .first()
    )
    if search is None:
        raise PermissionDenied("Candidate work unavailable")
    _validate_source_access(membership=membership, search=search, candidate_id=candidate_id)
    if opening_id is not None:
        if search.derived_opening_id != opening_id:
            raise ValidationError({"opening_id": "Opening must match the originating search."})
        authorize_opening(membership, search.derived_opening, "opening.read")
    elif search.derived_opening_id is not None:
        opening_id = search.derived_opening_id
    _authorize_membership(
        membership,
        action="candidate_work.write",
        tenant_id=membership.tenant_id,
        object_id=candidate_id,
    )
    defaults = {
        "opening_id": opening_id,
        "created_by": membership.identity,
        "updated_by": membership.identity,
    }
    try:
        record, created = CandidateWorkRecord.objects.get_or_create(
            tenant_id=membership.tenant_id,
            candidate_profile_id=candidate_id,
            originating_search=search,
            defaults=defaults,
        )
    except IntegrityError:
        record = CandidateWorkRecord.objects.get(
            tenant_id=membership.tenant_id,
            candidate_profile_id=candidate_id,
            originating_search=search,
        )
        created = False
    if record.opening_id != opening_id:
        raise ValidationError({"opening_id": "Existing candidate work has another context."})
    record_recruiting_event(
        actor=membership.identity,
        tenant_id=record.tenant_id,
        action="CANDIDATE_WORK_CREATED" if created else "CANDIDATE_WORK_VIEWED",
        target_type="candidate_work",
        target_id=record.id,
        trigger=trigger,
        originating_search_id=str(search.id),
    )
    if created:
        from modules.operations.outbox import enqueue

        enqueue(
            aggregate_type="candidate_work",
            aggregate_id=record.id,
            aggregate_version=record.version,
            event_type="candidate_work.created.v1",
            payload={
                "candidate_work_id": str(record.id),
                "originating_search_id": str(search.id),
            },
            idempotency_key=f"candidate-work-created:{record.id}",
            tenant_id=record.tenant_id,
            actor_id=membership.identity_id,
        )
    return record, created


def get_candidate_work(*, membership, candidate_work_id) -> CandidateWorkRecord:
    record = CandidateWorkRecord.objects.select_related(
        "opening", "originating_search", "candidate_profile"
    ).get(pk=candidate_work_id, tenant_id=membership.tenant_id)
    authorize_candidate_work(membership, record, "candidate_work.read")
    return record


@transaction.atomic
def link_application_candidate_work(application: Application) -> CandidateWorkRecord | None:
    if application.candidate_work_record_id:
        return CandidateWorkRecord.objects.filter(pk=application.candidate_work_record_id).first()
    record = (
        CandidateWorkRecord.objects.filter(
            tenant_id=application.tenant_id,
            candidate_profile_id=application.candidate_profile_id,
        )
        .filter(models.Q(opening_id=application.opening_id) | models.Q(opening__isnull=True))
        .order_by(models.F("opening_id").desc(nulls_last=True), "-updated_at")
        .first()
    )
    if record is not None:
        Application.objects.filter(pk=application.pk, candidate_work_record_id__isnull=True).update(
            candidate_work_record_id=record.id
        )
        application.candidate_work_record_id = record.id
    return record


from django.db import models  # noqa: E402
