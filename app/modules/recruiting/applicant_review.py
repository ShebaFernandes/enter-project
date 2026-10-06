from __future__ import annotations

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.utils import timezone

from modules.candidate.models import CandidateProfile, ResumeAsset
from modules.candidate.resume_processing import storage_client
from modules.candidate.serializers import employment_record_data
from modules.operations.concurrency import strong_etag
from modules.tenancy.policy import authorize_opening

from .application_models import Application
from .models import Opening


def _application_scope(application: Application, field: str) -> bool:
    consent = application.consent_context
    return bool(
        consent
        and consent.purpose == "APPLICATION_SUBMISSION"
        and consent.withdrawn_at is None
        and consent.expires_at > timezone.now()
        and field in consent.field_scope
        and consent.audience_scope.get("tenant_id") == str(application.tenant_id)
        and consent.audience_scope.get("opening_id") == str(application.opening_id)
    )


def _profile_name(profile: CandidateProfile) -> str:
    from modules.operations.crypto import decrypt

    try:
        return decrypt(bytes(profile.full_name_ciphertext)) if profile.full_name_ciphertext else ""
    except Exception as exc:  # pragma: no cover - encrypted storage failure is fail-closed
        raise PermissionDenied("Candidate profile unavailable") from exc


def applicant_data(application: Application) -> dict[str, object]:
    profile = CandidateProfile.objects.prefetch_related(
        "skills", "links", "employment_history"
    ).get(pk=application.candidate_profile_id)
    resume = application.resume
    resume_available = bool(
        resume
        and _application_scope(application, "resume")
        and resume.scan_status == ResumeAsset.ScanStatus.CLEAN
        and resume.parse_status == ResumeAsset.ParseStatus.READY
        and resume.clean_key
    )
    data: dict[str, object] = {
        "id": str(application.id),
        "candidate_id": str(profile.id),
        "name": (
            _profile_name(profile) if _application_scope(application, "profile") else "Candidate"
        ),
        "headline": (profile.headline if _application_scope(application, "profile") else None),
        "current_role": (
            profile.current_role if _application_scope(application, "profile") else None
        ),
        "current_company": (
            profile.current_company if _application_scope(application, "profile") else None
        ),
        "location": profile.location if _application_scope(application, "profile") else {},
        "experience_years": (
            profile.experience_years if _application_scope(application, "profile") else None
        ),
        "education": profile.education if _application_scope(application, "profile") else [],
        "skills": (
            list(profile.skills.values_list("display_name", flat=True))
            if _application_scope(application, "profile")
            else []
        ),
        "employment_history": (
            [employment_record_data(item) for item in profile.employment_history.all()]
            if _application_scope(application, "employment_history")
            else []
        ),
        "professional_links": (
            list(profile.links.values_list("normalized_url", flat=True))
            if _application_scope(application, "professional_links")
            else []
        ),
        "motivation": application.answers.get("motivation", ""),
        "candidate_status": application.candidate_status,
        "internal_status": application.internal_status,
        "submitted_at": application.submitted_at,
        "version": application.version,
        "etag": strong_etag(application.id, application.version),
        "resume_available": resume_available,
        "resume_url": (
            f"/api/v1/tenants/{application.tenant_id}/applications/{application.id}/resume"
        ),
    }
    return data


def applications_for_opening(*, membership, opening: Opening) -> list[dict[str, object]]:
    authorize_opening(membership, opening, "opening.read")
    applications = (
        Application.objects.select_related("consent_context", "resume")
        .filter(
            tenant_id=membership.tenant_id,
            opening=opening,
            state__in=[Application.State.SUBMITTED, Application.State.ACTIVE],
        )
        .order_by("-submitted_at")
    )
    return [applicant_data(application) for application in applications]


def applicant_resume(*, membership, application_id) -> FileResponse:
    application = (
        Application.objects.select_related("opening", "consent_context", "resume")
        .filter(pk=application_id, tenant_id=membership.tenant_id)
        .first()
    )
    if application is None:
        raise PermissionDenied("Application unavailable")
    authorize_opening(membership, application.opening, "opening.read")
    if not _application_scope(application, "resume") or application.resume is None:
        raise PermissionDenied("Resume unavailable")
    resume = application.resume
    if (
        resume.scan_status != ResumeAsset.ScanStatus.CLEAN
        or resume.parse_status != ResumeAsset.ParseStatus.READY
        or not resume.clean_key
    ):
        raise PermissionDenied("Resume unavailable")
    try:
        stored = storage_client().get_object(
            Bucket=settings.RESUME_QUARANTINE_BUCKET, Key=resume.clean_key
        )
    except Exception as exc:
        raise PermissionDenied("Resume temporarily unavailable") from exc
    extension = {"application/pdf": "pdf", "application/msword": "doc"}.get(
        resume.detected_mime, "docx"
    )
    response = FileResponse(
        stored["Body"],
        as_attachment=False,
        filename=f"resume.{extension}",
        content_type=resume.detected_mime or resume.declared_mime,
    )
    response["Cache-Control"] = "no-store, private"
    return response
