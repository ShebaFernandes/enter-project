from __future__ import annotations

import hashlib
import secrets
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


@dataclass(frozen=True)
class LocalRecruiterBootstrap:
    token: str
    tenant_id: str
    recruiter_id: str
    candidate_id: str


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
        Opening.objects.update_or_create(
            tenant=tenant,
            business_unit=unit,
            title="Software Engineer",
            defaults={
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


def _token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode()).hexdigest()
    return f"local-synthetic-recruiter-bootstrap:{digest}"
