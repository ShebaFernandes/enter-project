from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from modules.audit.service import record_audit_event
from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import AuthorizationRequest, authorize

from .models import RecruiterEnteredCandidate


def _require_synthetic_environment() -> None:
    if settings.ENV.app_env not in {"local", "test"}:
        raise PermissionDenied("Recruiter-entered candidates are unavailable")


@transaction.atomic
def create_recruiter_entered_candidate(
    *, membership: TenantMembership, actor, values: dict
) -> RecruiterEnteredCandidate:
    _require_synthetic_environment()
    authorize(
        AuthorizationRequest(
            action="recruiter_candidate.create",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
            actor=actor,
        )
    )
    if membership.role != TenantMembership.Role.RECRUITER:
        raise PermissionDenied("Operation unavailable")
    if values.pop("confirm_synthetic", False) is not True:
        raise ValidationError("Synthetic provenance confirmation is required")
    candidate = RecruiterEnteredCandidate(
        tenant=membership.tenant,
        created_by=actor,
        display_name=values["display_name"],
        location=values["location"],
        experience_years=Decimal(str(values["experience_years"])),
        skills=values["skills"],
    )
    candidate.full_clean()
    candidate.save()
    record_audit_event(
        actor=actor,
        effective_role=membership.role,
        tenant_id=membership.tenant_id,
        action="RECRUITER_SYNTHETIC_CANDIDATE_CREATE",
        target_type="recruiter_entered_candidate",
        target_id=str(candidate.id),
        outcome="ALLOWED",
    )
    return candidate


def list_recruiter_entered_candidates(*, membership: TenantMembership):
    _require_synthetic_environment()
    authorize(
        AuthorizationRequest(
            action="recruiter_candidate.read",
            role=membership.role,
            tenant_id=membership.tenant_id,
            object_tenant_id=membership.tenant_id,
        )
    )
    return RecruiterEnteredCandidate.objects.filter(tenant_id=membership.tenant_id).order_by(
        "created_at", "id"
    )
