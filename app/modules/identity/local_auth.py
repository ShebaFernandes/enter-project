from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone

from modules.candidate.finding_evaluators import evaluate_employment_record
from modules.candidate.models import (
    CandidateProfile,
    CandidateSkill,
    ConsentRecord,
    EmploymentRecord,
    ProfileLink,
    ResumeAsset,
    VisibilityRule,
)
from modules.operations.crypto import encrypt
from modules.recruiting.models import Opening
from modules.tenancy.models import BusinessUnit, Tenant, TenantMembership

from .models import Identity
from .services import link_identity_with_role

TOKEN_TTL_SECONDS = 600
RECRUITER_SUBJECT = "local-synthetic-recruiter"
CANDIDATE_SUBJECT = "local-synthetic-candidate"
COMPARISON_CANDIDATE_SUBJECT = "local-synthetic-comparison-candidate"
TENANT_ADMIN_SUBJECT = "local-synthetic-tenant-admin"
BASE_OPENING_ID = uuid.UUID("00000000-0000-4000-8000-000000000106")
logger = logging.getLogger(__name__)


def _synthetic_resume_pdf() -> bytes:
    stream = (
        b"BT /F1 18 Tf 72 740 Td (Synthetic Search Candidate) Tj "
        b"0 -30 Td /F1 11 Tf (Senior Backend Engineer - Python, Django, PostgreSQL) Tj "
        b"0 -22 Td (Education: B.Tech Computer Science, Bengaluru Institute of Technology) Tj ET"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(document)


@dataclass(frozen=True)
class LocalRecruiterBootstrap:
    token: str
    tenant_id: str
    recruiter_id: str
    candidate_id: str


@dataclass(frozen=True)
class LocalCandidateBootstrap:
    token: str
    candidate_id: str
    opening_id: str


@dataclass(frozen=True)
class LocalTenantAdminBootstrap:
    token: str
    tenant_id: str
    tenant_admin_id: str


def _require_local_test() -> None:
    if not settings.LOCAL_SYNTHETIC_AUTH_ENABLED or settings.ENV.app_env not in {
        "local",
        "test",
    }:
        raise PermissionDenied("Local synthetic authentication is unavailable")


@contextmanager
def _rls_context(*, tenant_id=None, identity_id=None):
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                if tenant_id is not None:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])
                if identity_id is not None:
                    cursor.execute(
                        "SELECT set_config('app.identity_id', %s, true)", [str(identity_id)]
                    )
        yield


def _synthetic_identity(*, subject: str, email: str, workforce: bool) -> Identity:
    claims: dict[str, object] = {
        "sub": subject,
        "email": email,
        "email_verified": True,
        "amr": ["mfa"] if workforce else ["email"],
    }
    return link_identity_with_role(claims, workforce=workforce)


def seed_local_recruiter_verification() -> tuple[Identity, Tenant, CandidateProfile]:
    _require_local_test()
    recruiter = _synthetic_identity(
        subject=RECRUITER_SUBJECT,
        email="recruiter@local-synthetic.invalid",
        workforce=True,
    )
    admin = _synthetic_identity(
        subject="synthetic-tenant-admin",
        email="admin@local-synthetic.invalid",
        workforce=True,
    )
    tenant, _ = Tenant.objects.update_or_create(
        slug="local-synthetic-recruiting",
        defaults={
            "name": "Local Synthetic Recruiting",
            "legal_boundary_reference": "LOCAL-SYNTHETIC-ONLY",
            "status": Tenant.Status.ACTIVE,
        },
    )
    with _rls_context(tenant_id=tenant.id):
        TenantMembership.objects.update_or_create(
            tenant=tenant,
            identity=recruiter,
            defaults={
                "role": TenantMembership.Role.RECRUITER,
                "status": TenantMembership.Status.ACTIVE,
                "scope": {},
            },
        )
        TenantMembership.objects.update_or_create(
            tenant=tenant,
            identity=admin,
            defaults={
                "role": TenantMembership.Role.TENANT_ADMIN,
                "status": TenantMembership.Status.ACTIVE,
                "scope": {},
            },
        )
        unit, _ = BusinessUnit.objects.update_or_create(
            tenant=tenant,
            name="Synthetic Engineering",
            defaults={"created_by": admin, "status": BusinessUnit.Status.ACTIVE},
        )
        opening, _ = Opening.objects.update_or_create(
            id=BASE_OPENING_ID,
            defaults={
                "tenant": tenant,
                "business_unit": unit,
                "title": "Software Engineer",
                "location": {"normalized": "bengaluru", "display": "Bengaluru"},
                "work_mode": Opening.WorkMode.REMOTE,
                "employment_type": "PERMANENT",
                "state": Opening.State.OPEN,
                "created_by": admin,
            },
        )

    candidate_identity = _synthetic_identity(
        subject=CANDIDATE_SUBJECT,
        email="candidate@local-synthetic.invalid",
        workforce=False,
    )
    with _rls_context(identity_id=candidate_identity.id):
        profile, _ = CandidateProfile.objects.update_or_create(
            identity=candidate_identity,
            defaults={
                "full_name_ciphertext": encrypt("Synthetic Search Candidate"),
                "location": {"normalized": "bengaluru", "display": "Bengaluru"},
                "headline": "Backend engineer",
                "current_role": "Software Engineer",
                "current_company": "Synthetic Current Employer",
                "experience_years": "5.00",
                # Exact category membership matches the local prompt's "engineer";
                # retain the opening-title category for existing synthetic journeys.
                "role_categories": ["engineer", "software engineer"],
                "preferred_locations": ["bengaluru"],
                "work_arrangements": ["REMOTE"],
                "education": [
                    {
                        "school": "Bengaluru Institute of Technology",
                        "degree": "B.Tech",
                        "field_of_study": "Computer Science",
                        "start_year": 2016,
                        "end_year": 2020,
                    }
                ],
                "profile_state": CandidateProfile.State.PUBLISHED,
                "consent_expires_at": timezone.now() + timedelta(days=365),
            },
        )
        CandidateSkill.objects.update_or_create(
            profile=profile,
            normalized_name="python",
            defaults={"display_name": "Python", "ordering": 0},
        )
        ProfileLink.objects.update_or_create(
            profile=profile,
            normalized_url="https://www.linkedin.com/in/synthetic-search-candidate",
            defaults={"display_label": "LinkedIn", "ordering": 0},
        )
        ProfileLink.objects.update_or_create(
            profile=profile,
            normalized_url="https://github.com/synthetic-search-candidate",
            defaults={"display_label": "GitHub", "ordering": 1},
        )
        consent, _ = ConsentRecord.objects.update_or_create(
            profile=profile,
            source_request_id="local-synthetic-recruiter-verification",
            defaults={
                "purpose": "RECRUITING_DISCOVERY",
                "field_scope": ["profile", "employment_history", "skills", "resume"],
                "audience_scope": {"approved_tenant_ids": [str(tenant.id)]},
                "notice_version": "candidate-discovery-v1",
                "affirmative_action": "LOCAL_SYNTHETIC_FIXTURE",
                "expires_at": timezone.now() + timedelta(days=365),
                "withdrawn_at": None,
            },
        )
        VisibilityRule.objects.filter(profile=profile, superseded_at__isnull=True).exclude(
            consent_record=consent
        ).update(superseded_at=timezone.now())
        VisibilityRule.objects.update_or_create(
            profile=profile,
            consent_record=consent,
            defaults={
                "mode": VisibilityRule.Mode.APPROVED_RECRUITERS,
                "approved_tenant_ids": [str(tenant.id)],
                "matching_preferences": {},
                "actor": candidate_identity,
                "superseded_at": None,
            },
        )
        employment, _ = EmploymentRecord.objects.update_or_create(
            profile=profile,
            company="Synthetic Previous Employer",
            defaults={
                "role_title": "Software Engineer",
                "start_date": date(2025, 1, 1),
                "end_date": date(2025, 9, 1),
                "start_date_state": EmploymentRecord.ValueState.CONFIRMED,
                "end_date_state": EmploymentRecord.ValueState.CONFIRMED,
                "start_date_precision": EmploymentRecord.DatePrecision.DAY,
                "end_date_precision": EmploymentRecord.DatePrecision.DAY,
                "is_current": False,
                "employment_type": EmploymentRecord.EmploymentType.PERMANENT,
                "employment_type_state": EmploymentRecord.ValueState.CONFIRMED,
                "provenance": EmploymentRecord.Provenance.CANDIDATE_REPORTED,
                "version": 1,
            },
        )
        profile.findings.filter(code="SHORT_TENURE", superseded_at__isnull=True).exclude(
            source_record_id=employment.id
        ).update(superseded_at=timezone.now())
        evaluate_employment_record(employment)
        synthetic_resume = _synthetic_resume_pdf()
        synthetic_resume_sha256 = hashlib.sha256(synthetic_resume).hexdigest()
        resume = ResumeAsset.objects.filter(profile=profile, is_current=True).first()
        if resume is None:
            resume = ResumeAsset.objects.create(
                profile=profile,
                quarantine_key=f"quarantine/local-synthetic/{profile.id}",
                clean_key=f"clean/local-synthetic/{profile.id}",
                original_filename_ciphertext=encrypt("synthetic-resume.pdf"),
                declared_mime="application/pdf",
                detected_mime="application/pdf",
                size_bytes=len(synthetic_resume),
                sha256=synthetic_resume_sha256,
                scan_status=ResumeAsset.ScanStatus.CLEAN,
                parse_status=ResumeAsset.ParseStatus.READY,
            )
        else:
            # The local synthetic identity is reused between learning exercises.
            # Restore the fixture promised by this bootstrap after failure drills.
            resume.scan_status = ResumeAsset.ScanStatus.CLEAN
            resume.parse_status = ResumeAsset.ParseStatus.READY
            resume.deleted_at = None
            resume.size_bytes = len(synthetic_resume)
            resume.sha256 = synthetic_resume_sha256
            resume.save(
                update_fields=[
                    "scan_status",
                    "parse_status",
                    "deleted_at",
                    "size_bytes",
                    "sha256",
                ]
            )
        try:
            from modules.candidate.resume_processing import storage_client

            storage_client().put_object(
                Bucket=settings.RESUME_QUARANTINE_BUCKET,
                Key=resume.clean_key,
                Body=synthetic_resume,
                ContentType="application/pdf",
            )
        except Exception as exc:
            # LocalStack may still be starting. The profile remains usable and the
            # next synthetic bootstrap retries the deterministic upload.
            logger.warning(
                "Synthetic resume upload deferred",
                extra={"error_type": type(exc).__name__},
            )
        ConsentRecord.objects.update_or_create(
            profile=profile,
            source_request_id=f"local-application-{opening.id}",
            defaults={
                "purpose": "APPLICATION_SUBMISSION",
                "field_scope": ["application", "resume", "notifications"],
                "audience_scope": {
                    "tenant_id": str(tenant.id),
                    "opening_id": str(opening.id),
                },
                "notice_version": "application-v1",
                "affirmative_action": "LOCAL_SYNTHETIC_FIXTURE",
                "expires_at": timezone.now() + timedelta(days=365),
                "withdrawn_at": None,
            },
        )

    comparison_identity = _synthetic_identity(
        subject=COMPARISON_CANDIDATE_SUBJECT,
        email="comparison-candidate@local-synthetic.invalid",
        workforce=False,
    )
    with _rls_context(identity_id=comparison_identity.id):
        comparison_profile, _ = CandidateProfile.objects.update_or_create(
            identity=comparison_identity,
            defaults={
                "full_name_ciphertext": encrypt("Synthetic Comparison Candidate"),
                "location": {"normalized": "bengaluru", "display": "Bengaluru"},
                "headline": "Platform engineer",
                "current_role": "Platform Engineer",
                "current_company": "Synthetic Platform Employer",
                "experience_years": "6.00",
                "role_categories": ["software engineer"],
                "preferred_locations": ["bengaluru"],
                "work_arrangements": ["REMOTE"],
                "education": [
                    {
                        "school": "National Institute of Technology Karnataka",
                        "degree": "B.E.",
                        "field_of_study": "Information Technology",
                        "start_year": 2015,
                        "end_year": 2019,
                    }
                ],
                "notice_period": "Unknown",
                "profile_state": CandidateProfile.State.PUBLISHED,
                "consent_expires_at": timezone.now() + timedelta(days=365),
            },
        )
        CandidateSkill.objects.update_or_create(
            profile=comparison_profile,
            normalized_name="python",
            defaults={"display_name": "Python", "ordering": 0},
        )
        ProfileLink.objects.update_or_create(
            profile=comparison_profile,
            normalized_url="https://www.linkedin.com/in/synthetic-comparison-candidate",
            defaults={"display_label": "LinkedIn", "ordering": 0},
        )
        ProfileLink.objects.update_or_create(
            profile=comparison_profile,
            normalized_url="https://github.com/synthetic-comparison-candidate",
            defaults={"display_label": "GitHub", "ordering": 1},
        )
        comparison_consent, _ = ConsentRecord.objects.update_or_create(
            profile=comparison_profile,
            source_request_id="local-synthetic-comparison-verification",
            defaults={
                "purpose": "RECRUITING_DISCOVERY",
                "field_scope": ["profile", "employment_history", "skills", "resume"],
                "audience_scope": {"approved_tenant_ids": [str(tenant.id)]},
                "notice_version": "candidate-discovery-v1",
                "affirmative_action": "LOCAL_SYNTHETIC_FIXTURE",
                "expires_at": timezone.now() + timedelta(days=365),
                "withdrawn_at": None,
            },
        )
        VisibilityRule.objects.filter(
            profile=comparison_profile, superseded_at__isnull=True
        ).exclude(consent_record=comparison_consent).update(superseded_at=timezone.now())
        VisibilityRule.objects.update_or_create(
            profile=comparison_profile,
            consent_record=comparison_consent,
            defaults={
                "mode": VisibilityRule.Mode.APPROVED_RECRUITERS,
                "approved_tenant_ids": [str(tenant.id)],
                "matching_preferences": {},
                "actor": comparison_identity,
                "superseded_at": None,
            },
        )
    return recruiter, tenant, profile


def issue_local_recruiter_bootstrap() -> LocalRecruiterBootstrap:
    recruiter, tenant, profile = seed_local_recruiter_verification()
    token = secrets.token_urlsafe(32)
    cache.set(
        _token_key(token),
        {"recruiter_id": str(recruiter.id), "tenant_id": str(tenant.id)},
        timeout=TOKEN_TTL_SECONDS,
    )
    return LocalRecruiterBootstrap(token, str(tenant.id), str(recruiter.id), str(profile.id))


def consume_local_recruiter_bootstrap(token: str) -> tuple[Identity, TenantMembership]:
    _require_local_test()
    if len(token) < 32:
        raise PermissionDenied("Synthetic session unavailable")
    key = _token_key(token)
    payload = cache.get(key)
    if not isinstance(payload, dict) or cache.delete(key) != 1:
        raise PermissionDenied("Synthetic session unavailable")
    recruiter_id = payload.get("recruiter_id")
    tenant_id = payload.get("tenant_id")
    if not isinstance(recruiter_id, str) or not isinstance(tenant_id, str):
        raise PermissionDenied("Synthetic session unavailable")
    identity = Identity.objects.filter(
        pk=recruiter_id,
        cognito_subject=RECRUITER_SUBJECT,
        status=Identity.Status.ACTIVE,
    ).first()
    if identity is None:
        raise PermissionDenied("Synthetic session unavailable")
    with _rls_context(tenant_id=tenant_id):
        membership = TenantMembership.objects.filter(
            tenant_id=tenant_id,
            identity=identity,
            role=TenantMembership.Role.RECRUITER,
            status=TenantMembership.Status.ACTIVE,
            tenant__status=Tenant.Status.ACTIVE,
        ).first()
    if membership is None:
        raise PermissionDenied("Synthetic session unavailable")
    return identity, membership


def issue_local_tenant_admin_bootstrap() -> LocalTenantAdminBootstrap:
    _, tenant, _ = seed_local_recruiter_verification()
    admin = _synthetic_identity(
        subject=TENANT_ADMIN_SUBJECT,
        email="tenant-admin@local-synthetic.invalid",
        workforce=True,
    )
    with _rls_context(tenant_id=tenant.id):
        TenantMembership.objects.update_or_create(
            tenant=tenant,
            identity=admin,
            defaults={
                "role": TenantMembership.Role.TENANT_ADMIN,
                "status": TenantMembership.Status.ACTIVE,
                "scope": {},
            },
        )
    token = secrets.token_urlsafe(32)
    cache.set(
        _tenant_admin_token_key(token),
        {"tenant_admin_id": str(admin.id), "tenant_id": str(tenant.id)},
        timeout=TOKEN_TTL_SECONDS,
    )
    return LocalTenantAdminBootstrap(token, str(tenant.id), str(admin.id))


def consume_local_tenant_admin_bootstrap(token: str) -> tuple[Identity, TenantMembership]:
    _require_local_test()
    if len(token) < 32:
        raise PermissionDenied("Synthetic session unavailable")
    key = _tenant_admin_token_key(token)
    payload = cache.get(key)
    if not isinstance(payload, dict) or cache.delete(key) != 1:
        raise PermissionDenied("Synthetic session unavailable")
    admin_id = payload.get("tenant_admin_id")
    tenant_id = payload.get("tenant_id")
    if not isinstance(admin_id, str) or not isinstance(tenant_id, str):
        raise PermissionDenied("Synthetic session unavailable")
    identity = Identity.objects.filter(
        pk=admin_id,
        cognito_subject=TENANT_ADMIN_SUBJECT,
        status=Identity.Status.ACTIVE,
    ).first()
    if identity is None:
        raise PermissionDenied("Synthetic session unavailable")
    with _rls_context(tenant_id=tenant_id):
        membership = TenantMembership.objects.filter(
            tenant_id=tenant_id,
            identity=identity,
            role=TenantMembership.Role.TENANT_ADMIN,
            status=TenantMembership.Status.ACTIVE,
            tenant__status=Tenant.Status.ACTIVE,
        ).first()
    if membership is None:
        raise PermissionDenied("Synthetic session unavailable")
    return identity, membership


def issue_local_candidate_bootstrap() -> LocalCandidateBootstrap:
    recruiter, tenant, profile = seed_local_recruiter_verification()
    admin = Identity.objects.get(cognito_subject="synthetic-tenant-admin")
    with _rls_context(tenant_id=tenant.id):
        unit = BusinessUnit.objects.filter(tenant=tenant, status=BusinessUnit.Status.ACTIVE).first()
        if unit is None:
            raise PermissionDenied("Synthetic session unavailable")
        opening = Opening.objects.get(pk=BASE_OPENING_ID, tenant=tenant)
        from modules.recruiting.public_openings import publication_preview, synchronize_publication

        membership = TenantMembership.objects.get(
            tenant=tenant,
            identity=admin,
            role=TenantMembership.Role.TENANT_ADMIN,
            status=TenantMembership.Status.ACTIVE,
        )
        preview = publication_preview(opening)
        if preview["publication_state"] != "PUBLISHED":
            synchronize_publication(
                opening=opening,
                membership=membership,
                confirmed=True,
                if_match=preview["source_etag"],
                preview_digest=preview["preview_digest"],
            )
        public_id = opening.openingpublicationlink.public_id
    with _rls_context(identity_id=profile.identity_id):
        ConsentRecord.objects.update_or_create(
            profile=profile,
            purpose="APPLICATION_SUBMISSION",
            source_request_id=f"local-application-{opening.id}",
            defaults={
                "field_scope": [
                    "application",
                    "profile",
                    "resume",
                    "employment_history",
                    "professional_links",
                    "notifications",
                ],
                "audience_scope": {
                    "tenant_id": str(tenant.id),
                    "opening_id": str(opening.id),
                },
                "notice_version": "application-v1",
                "affirmative_action": "LOCAL_SYNTHETIC_FIXTURE",
                "expires_at": timezone.now() + timedelta(days=365),
                "withdrawn_at": None,
            },
        )
    token = secrets.token_urlsafe(32)
    cache.set(
        _candidate_token_key(token),
        {
            "candidate_id": str(profile.identity_id),
            "opening_id": str(opening.id),
            "tenant_id": str(tenant.id),
        },
        timeout=TOKEN_TTL_SECONDS,
    )
    return LocalCandidateBootstrap(token, str(profile.identity_id), str(public_id))


def consume_local_candidate_bootstrap(token: str) -> tuple[Identity, Opening]:
    _require_local_test()
    if len(token) < 32:
        raise PermissionDenied("Synthetic session unavailable")
    key = _candidate_token_key(token)
    payload = cache.get(key)
    if not isinstance(payload, dict) or cache.delete(key) != 1:
        raise PermissionDenied("Synthetic session unavailable")
    candidate_id = payload.get("candidate_id")
    opening_id = payload.get("opening_id")
    tenant_id = payload.get("tenant_id")
    if (
        not isinstance(candidate_id, str)
        or not isinstance(opening_id, str)
        or not isinstance(tenant_id, str)
    ):
        raise PermissionDenied("Synthetic session unavailable")
    identity = Identity.objects.filter(
        pk=candidate_id,
        cognito_subject=CANDIDATE_SUBJECT,
        status=Identity.Status.ACTIVE,
    ).first()
    with _rls_context(tenant_id=tenant_id):
        opening = (
            Opening.objects.select_related("openingpublicationlink")
            .filter(pk=opening_id, state=Opening.State.OPEN)
            .first()
        )
    if identity is None or opening is None:
        raise PermissionDenied("Synthetic session unavailable")
    return identity, opening


def _token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"local-synthetic-recruiter-bootstrap:{digest}"


def _candidate_token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"local-synthetic-candidate-bootstrap:{digest}"


def _tenant_admin_token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"local-synthetic-tenant-admin-bootstrap:{digest}"
