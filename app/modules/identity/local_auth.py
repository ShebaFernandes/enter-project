from __future__ import annotations

import hashlib
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
        unit, _ = BusinessUnit.objects.update_or_create(
            tenant=tenant,
            name="Synthetic Engineering",
            defaults={"created_by": recruiter, "status": BusinessUnit.Status.ACTIVE},
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
                "created_by": recruiter,
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
                "role_categories": ["software engineer"],
                "preferred_locations": ["bengaluru"],
                "work_arrangements": ["REMOTE"],
                "profile_state": CandidateProfile.State.PUBLISHED,
                "consent_expires_at": timezone.now() + timedelta(days=365),
            },
        )
        CandidateSkill.objects.update_or_create(
            profile=profile,
            normalized_name="python",
            defaults={"display_name": "Python", "ordering": 0},
        )
        consent, _ = ConsentRecord.objects.update_or_create(
            profile=profile,
            source_request_id="local-synthetic-recruiter-verification",
            defaults={
                "purpose": "RECRUITING_DISCOVERY",
                "field_scope": ["profile", "employment_history", "skills"],
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
        evaluate_employment_record(employment)
        resume = ResumeAsset.objects.filter(profile=profile, is_current=True).first()
        if resume is None:
            resume = ResumeAsset.objects.create(
                profile=profile,
                quarantine_key=f"quarantine/local-synthetic/{profile.id}",
                clean_key=f"clean/local-synthetic/{profile.id}",
                original_filename_ciphertext=encrypt("synthetic-resume.pdf"),
                declared_mime="application/pdf",
                detected_mime="application/pdf",
                size_bytes=1024,
                sha256="a" * 64,
                scan_status=ResumeAsset.ScanStatus.CLEAN,
                parse_status=ResumeAsset.ParseStatus.READY,
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
        comparison_consent, _ = ConsentRecord.objects.update_or_create(
            profile=comparison_profile,
            source_request_id="local-synthetic-comparison-verification",
            defaults={
                "purpose": "RECRUITING_DISCOVERY",
                "field_scope": ["profile", "employment_history", "skills"],
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
    with _rls_context(tenant_id=tenant.id):
        unit = BusinessUnit.objects.filter(tenant=tenant, status=BusinessUnit.Status.ACTIVE).first()
        if unit is None:
            raise PermissionDenied("Synthetic session unavailable")
        opening = Opening.objects.create(
            tenant=tenant,
            business_unit=unit,
            title="Software Engineer",
            location={"normalized": "bengaluru", "display": "Bengaluru"},
            work_mode=Opening.WorkMode.REMOTE,
            employment_type="PERMANENT",
            state=Opening.State.OPEN,
            created_by=recruiter,
        )
        from modules.recruiting.public_openings import publication_preview, synchronize_publication

        membership = TenantMembership.objects.get(tenant=tenant, identity=recruiter)
        preview = publication_preview(opening)
        synchronize_publication(
            opening=opening,
            membership=membership,
            confirmed=True,
            if_match=preview["source_etag"],
            preview_digest=preview["preview_digest"],
        )
        public_id = opening.openingpublicationlink.public_id
    with _rls_context(identity_id=profile.identity_id):
        ConsentRecord.objects.create(
            profile=profile,
            purpose="APPLICATION_SUBMISSION",
            field_scope=["application", "resume", "notifications"],
            audience_scope={
                "tenant_id": str(tenant.id),
                "opening_id": str(opening.id),
            },
            notice_version="application-v1",
            affirmative_action="LOCAL_SYNTHETIC_FIXTURE",
            source_request_id=f"local-application-{opening.id}",
            expires_at=timezone.now() + timedelta(days=365),
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
