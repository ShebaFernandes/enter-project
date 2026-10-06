from __future__ import annotations

import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.candidate.models import CandidateProfile, ConsentRecord, ResumeAsset
from modules.candidate.services import profile_data, profile_for
from modules.operations.concurrency import require_match
from modules.operations.idempotency import IdempotencyConflict
from modules.operations.outbox import enqueue
from modules.tenancy.policy import AuthorizationRequest, authorize, authorize_opening

from .application_audit import record_application_event
from .application_models import (
    Application,
    ApplicationStatusEvent,
    ApplicationStatusPreview,
    CandidateFacingStatus,
)
from .models import Opening
from .statuses import candidate_status_suggestion


def _public_application_link(public_opening_id):
    from .public_openings import application_publication_link, available_publications, public_reader

    with public_reader():
        published = available_publications().filter(pk=str(public_opening_id)).exists()
    if not published:
        raise PermissionDenied("Application unavailable")
    return application_publication_link(str(public_opening_id))


def application_readiness(*, identity, public_opening_id) -> dict[str, object]:
    """Return only candidate-owned state needed to continue a public application."""
    profile = profile_for(identity)
    resume = (
        profile.resumes.filter(is_current=True, deleted_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    link = _public_application_link(public_opening_id)
    from modules.tenancy.context import tenant_context
    from modules.tenancy.rls import tenant_transaction

    token = tenant_context.set(link.tenant_id)
    try:
        with tenant_transaction():
            application = Application.objects.filter(
                opening_id=link.opening_id,
                candidate_profile_id=profile.id,
            ).first()
    finally:
        tenant_context.reset(token)
    return {
        "profile_name": profile_data(profile)["full_name"],
        "profile_state": profile.profile_state,
        "resume": (
            {
                "id": str(resume.id),
                "scan_status": resume.scan_status,
                "parse_status": resume.parse_status,
                "ready": resume.scan_status == ResumeAsset.ScanStatus.CLEAN
                and resume.parse_status == ResumeAsset.ParseStatus.READY,
            }
            if resume
            else None
        ),
        "already_applied": application is not None,
        "application_id": str(application.id) if application else None,
    }


@transaction.atomic
def prepare_application_consent(
    *, identity, public_opening_id, confirmed: bool, request_key: str
) -> dict[str, object]:
    if confirmed is not True:
        raise ValidationError({"confirmed": "Explicit application consent is required."})
    profile = profile_for(identity)
    resume = (
        profile.resumes.select_for_update()
        .filter(
            is_current=True,
            deleted_at__isnull=True,
            scan_status=ResumeAsset.ScanStatus.CLEAN,
            parse_status=ResumeAsset.ParseStatus.READY,
        )
        .first()
    )
    if resume is None:
        raise ValidationError(
            {"resume": "Review a clean, processed resume before confirming this application."}
        )
    link = _public_application_link(public_opening_id)
    from modules.tenancy.context import tenant_context
    from modules.tenancy.rls import tenant_transaction

    token = tenant_context.set(link.tenant_id)
    try:
        with tenant_transaction():
            if Application.objects.filter(
                opening_id=link.opening_id,
                candidate_profile_id=profile.id,
            ).exists():
                raise IdempotencyConflict("An application already exists for this role")
    finally:
        tenant_context.reset(token)
    consent = ConsentRecord.objects.create(
        profile=profile,
        purpose="APPLICATION_SUBMISSION",
        field_scope=[
            "application",
            "profile",
            "resume",
            "employment_history",
            "professional_links",
            "notifications",
        ],
        audience_scope={
            "tenant_id": str(link.tenant_id),
            "opening_id": str(link.opening_id),
        },
        notice_version="application-v1",
        affirmative_action="APPLICATION_FORM_CHECKBOX",
        source_request_id=f"application-consent:{request_key}"[:100],
        expires_at=timezone.now() + timedelta(days=365),
    )
    record_audit_event(
        actor=identity,
        action="APPLICATION_CONSENT_CAPTURED",
        target_type="consent_record",
        target_id=str(consent.id),
        tenant_id=link.tenant_id,
        purpose_code="APPLICATION_SUBMISSION",
        outcome="ALLOWED",
        metadata={
            "opening_id": str(link.opening_id),
            "notice_version": consent.notice_version,
        },
    )
    return {"resume_id": str(resume.id), "consent_record_id": str(consent.id)}


def _validate_submission_consent(
    *, profile: CandidateProfile, opening: Opening, consent_id
) -> ConsentRecord:
    now = timezone.now()
    consent = ConsentRecord.objects.filter(
        pk=consent_id,
        profile=profile,
        withdrawn_at__isnull=True,
        expires_at__gt=now,
        purpose="APPLICATION_SUBMISSION",
    ).first()
    if consent is None:
        raise ValidationError({"consent_record_id": "Current application consent is required."})
    if not {"application", "resume"}.issubset(set(consent.field_scope)):
        raise ValidationError({"consent_record_id": "Application consent scope is incomplete."})
    audience = consent.audience_scope
    if audience.get("opening_id") != str(opening.id) or audience.get("tenant_id") != str(
        opening.tenant_id
    ):
        raise ValidationError({"consent_record_id": "Consent does not cover this role."})
    return consent


@transaction.atomic
def submit_application(*, identity, values: dict[str, object], request_key: str) -> Application:
    # Only an authenticated candidate may resolve private publication linkage.
    # The anonymous directory/detail paths never enter this service.
    profile_for(identity)
    from modules.tenancy.context import tenant_context
    from modules.tenancy.rls import tenant_transaction

    from .public_openings import application_publication_link, available_publications, public_reader

    with public_reader():
        published = available_publications().filter(pk=str(values["opening_id"])).exists()
    if not published:
        # Preserve authenticated internal-ID callers with their existing role-specific
        # consent. An inactive public UUID cannot resolve as an internal opening UUID.
        return _submit_application(identity=identity, values=values, request_key=request_key)
    link = application_publication_link(str(values["opening_id"]))
    token = tenant_context.set(link.tenant_id)
    try:
        with tenant_transaction():
            return _submit_application(
                identity=identity,
                values={**values, "opening_id": str(link.opening_id)},
                request_key=request_key,
            )
    finally:
        tenant_context.reset(token)


def _submit_application(*, identity, values: dict[str, object], request_key: str) -> Application:
    profile = profile_for(identity)
    opening_id = uuid.UUID(str(values["opening_id"]))
    resume_id = uuid.UUID(str(values["resume_id"]))
    opening = Opening.objects.select_for_update().filter(pk=opening_id).first()
    if opening is None or opening.state != Opening.State.OPEN:
        raise ValidationError({"opening_id": "This role is not accepting applications."})
    if Application.objects.filter(opening=opening, candidate_profile_id=profile.id).exists():
        raise IdempotencyConflict("An application already exists for this role")
    resume = ResumeAsset.objects.filter(
        pk=resume_id,
        profile=profile,
        scan_status=ResumeAsset.ScanStatus.CLEAN,
        parse_status=ResumeAsset.ParseStatus.READY,
        deleted_at__isnull=True,
    ).first()
    if resume is None:
        raise ValidationError({"resume_id": "A clean candidate-owned resume is required."})
    consent = _validate_submission_consent(
        profile=profile, opening=opening, consent_id=values["consent_record_id"]
    )
    preferences = values["notification_preferences"]
    if not isinstance(preferences, dict):
        raise ValidationError(
            {"notification_preferences": "Notification preferences must be an object."}
        )
    submitted_at = timezone.now()
    application = Application(
        tenant=opening.tenant,
        opening=opening,
        candidate_profile_id=profile.id,
        resume=resume,
        state=Application.State.SUBMITTED,
        candidate_status=CandidateFacingStatus.APPLIED,
        answers=values["answers"],
        consent_context_id=consent.id,
        notify_email=bool(preferences["email"]),
        notify_whatsapp=bool(preferences["whatsapp"]),
        status_published_at=submitted_at,
        status_published_by=identity,
        submitted_at=submitted_at,
    )
    application.full_clean()
    application.save()
    from .candidate_work import link_application_candidate_work

    link_application_candidate_work(application)
    ApplicationStatusEvent.objects.create(
        tenant=opening.tenant,
        application=application,
        prior_state="",
        new_state=Application.State.SUBMITTED,
        published_candidate_status=CandidateFacingStatus.APPLIED,
        actor=identity,
        reason_code="CANDIDATE_SUBMISSION",
        idempotency_key=f"application-submitted:{request_key}",
    )
    enqueue(
        aggregate_type="application",
        aggregate_id=application.id,
        aggregate_version=application.version,
        event_type="application.submitted.v1",
        payload={"application_id": str(application.id), "opening_id": str(opening.id)},
        idempotency_key=f"application-submitted-event:{application.id}",
        tenant_id=opening.tenant_id,
        actor_id=identity.id,
    )
    record_application_event(
        actor=identity,
        application=application,
        action="APPLICATION_SUBMITTED",
        changed_fields=(
            "answers",
            "candidate_status",
            "consent_context_id",
            "notification_preferences",
            "submitted_at",
        ),
    )
    return application


def own_application(*, identity, application_id, for_update: bool = False) -> Application:
    profile = profile_for(identity)
    queryset = Application.objects.all()
    if for_update:
        queryset = queryset.select_for_update()
    application = queryset.filter(pk=application_id, candidate_profile_id=profile.id).first()
    if application is None:
        raise PermissionDenied("Application unavailable")
    return application


@transaction.atomic
def withdraw_application(
    *, identity, application_id, if_match: str | None, request_key: str
) -> Application:
    application = own_application(identity=identity, application_id=application_id, for_update=True)
    attempted = {"candidate_status": CandidateFacingStatus.WITHDRAWN, "confirm": True}
    require_match(
        if_match,
        object_id=application.id,
        version=application.version,
        current={"candidate_status": application.candidate_status, "version": application.version},
        attempted=attempted,
    )
    if application.candidate_status == CandidateFacingStatus.WITHDRAWN:
        return application
    prior_state = application.state
    application.state = Application.State.WITHDRAWN
    application.candidate_status = CandidateFacingStatus.WITHDRAWN
    application.suggested_candidate_status = None
    application.withdrawn_at = timezone.now()
    application.status_published_at = application.withdrawn_at
    application.status_published_by = identity
    application.version += 1
    application.full_clean()
    application.save()
    ApplicationStatusEvent.objects.create(
        tenant_id=application.tenant_id,
        application=application,
        prior_state=prior_state,
        new_state=Application.State.WITHDRAWN,
        published_candidate_status=CandidateFacingStatus.WITHDRAWN,
        actor=identity,
        reason_code="CANDIDATE_CONFIRMED_WITHDRAWAL",
        idempotency_key=f"application-withdrawn:{request_key}",
    )
    record_application_event(
        actor=identity,
        application=application,
        action="APPLICATION_WITHDRAWN",
        changed_fields=("candidate_status", "state", "withdrawn_at"),
    )
    return application


@transaction.atomic
def replace_notification_preferences(
    *, identity, application_id, if_match: str | None, values: dict[str, bool]
) -> Application:
    application = own_application(identity=identity, application_id=application_id, for_update=True)
    require_match(
        if_match,
        object_id=application.id,
        version=application.version,
        current={
            "email": application.notify_email,
            "whatsapp": application.notify_whatsapp,
        },
        attempted=dict(values),
    )
    application.notify_email = values["email"]
    application.notify_whatsapp = values["whatsapp"]
    application.version += 1
    application.save(update_fields=("notify_email", "notify_whatsapp", "version", "updated_at"))
    record_application_event(
        actor=identity,
        application=application,
        action="APPLICATION_NOTIFICATION_PREFERENCES_UPDATED",
        changed_fields=("notification_preferences",),
    )
    return application


def _authorize_status_actor(*, membership, application: Application, action: str) -> None:
    authorize_opening(membership, application.opening, action)
    if application.consent_context_id is None:
        raise PermissionDenied("Operation unavailable")
    consent = ConsentRecord.objects.filter(
        pk=application.consent_context_id,
        profile_id=application.candidate_profile_id,
        purpose="APPLICATION_SUBMISSION",
        withdrawn_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if consent is None or "application" not in consent.field_scope:
        raise PermissionDenied("Operation unavailable")
    if consent.audience_scope.get("opening_id") != str(
        application.opening_id
    ) or consent.audience_scope.get("tenant_id") != str(application.tenant_id):
        raise PermissionDenied("Operation unavailable")
    authorize(
        AuthorizationRequest(
            action=action,
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=application.tenant_id,
            object_id=str(application.id),
            actor=membership.identity,
        )
    )


@transaction.atomic
def preview_candidate_status(
    *, membership, application_id, internal_status: str, if_match: str | None
) -> ApplicationStatusPreview:
    application = Application.objects.select_for_update().get(
        pk=application_id, tenant_id=membership.tenant_id
    )
    _authorize_status_actor(
        membership=membership, application=application, action="application.status.publish"
    )
    require_match(
        if_match,
        object_id=application.id,
        version=application.version,
        current={"candidate_status": application.candidate_status, "version": application.version},
        attempted={"internal_status": internal_status},
    )
    suggestion = candidate_status_suggestion(internal_status)
    application.suggested_candidate_status = suggestion
    application.version += 1
    application.save(update_fields=("suggested_candidate_status", "version", "updated_at"))
    preview = ApplicationStatusPreview.objects.create(
        tenant_id=application.tenant_id,
        application=application,
        actor=membership.identity,
        internal_status=internal_status,
        suggested_candidate_status=suggestion,
        application_version=application.version,
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    ApplicationStatusEvent.objects.create(
        tenant_id=application.tenant_id,
        application=application,
        prior_state="",
        new_state=internal_status,
        suggested_candidate_status=suggestion,
        actor=membership.identity,
        reason_code="STATUS_PREVIEW",
        idempotency_key=f"status-preview:{preview.id}",
    )
    record_application_event(
        actor=membership.identity,
        application=application,
        action="APPLICATION_STATUS_PREVIEWED",
        changed_fields=("suggested_candidate_status",),
    )
    return preview


@transaction.atomic
def publish_candidate_status(
    *,
    membership,
    application_id,
    preview_id,
    candidate_status: str,
    if_match: str | None,
    request_key: str,
) -> Application:
    application = Application.objects.select_for_update().get(
        pk=application_id, tenant_id=membership.tenant_id
    )
    _authorize_status_actor(
        membership=membership, application=application, action="application.status.publish"
    )
    require_match(
        if_match,
        object_id=application.id,
        version=application.version,
        current={"candidate_status": application.candidate_status, "version": application.version},
        attempted={"candidate_status": candidate_status, "confirm": True},
    )
    preview = (
        ApplicationStatusPreview.objects.select_for_update()
        .filter(
            pk=preview_id,
            application=application,
            actor=membership.identity,
            application_version=application.version,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if preview is None:
        raise ValidationError({"preview_id": "A current preview by this recruiter is required."})
    prior = application.candidate_status
    application.candidate_status = candidate_status
    application.suggested_candidate_status = None
    application.status_published_at = timezone.now()
    application.status_published_by = membership.identity
    application.version += 1
    application.save()
    preview.consumed_at = timezone.now()
    preview.save(update_fields=("consumed_at",))
    ApplicationStatusEvent.objects.create(
        tenant_id=application.tenant_id,
        application=application,
        prior_state=prior,
        new_state=application.internal_status,
        suggested_candidate_status=preview.suggested_candidate_status,
        published_candidate_status=candidate_status,
        actor=membership.identity,
        reason_code="RECRUITER_CONFIRMED_PUBLICATION",
        idempotency_key=f"status-publication:{request_key}",
    )
    enqueue(
        aggregate_type="application",
        aggregate_id=application.id,
        aggregate_version=application.version,
        event_type="application.candidate_status_publish_requested.v1",
        payload={"candidate_status": candidate_status, "application_id": str(application.id)},
        idempotency_key=f"status-publication-event:{request_key}",
        tenant_id=application.tenant_id,
        actor_id=membership.identity_id,
    )
    record_application_event(
        actor=membership.identity,
        application=application,
        action="APPLICATION_STATUS_PUBLISHED",
        changed_fields=("candidate_status", "status_published_at"),
    )
    return application
