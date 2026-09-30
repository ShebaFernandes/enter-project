from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.candidate.models import ConsentRecord
from modules.recruiting.disclosures import (
    confirm_disclosure,
    preview_disclosure,
    record_disclosure_result,
)
from modules.tenancy.models import AccessGrant
from tests.factories import ApplicationFactory, MembershipFactory, TenantFactory


def disclosure_consent_and_grant(*, application, recruiter, fields):
    consent = ConsentRecord.objects.create(
        profile_id=application.candidate_profile_id,
        purpose="HIRING_TEAM_SHARE",
        field_scope=fields,
        audience_scope={
            "tenant_id": str(application.tenant_id),
            "opening_id": str(application.opening_id),
        },
        notice_version="v1",
        affirmative_action="DISCLOSURE_CONSENT",
        source_request_id=f"synthetic-disclosure-{application.id}",
        expires_at=timezone.now() + timedelta(days=30),
    )
    grant = AccessGrant.objects.create(
        tenant_id=application.tenant_id,
        grantee=recruiter.identity,
        purpose_code="HIRING_TEAM_SHARE",
        field_scope=fields,
        object_scope={"ids": [str(application.id)]},
        valid_from=timezone.now() - timedelta(minutes=1),
        expires_at=timezone.now() + timedelta(hours=1),
    )
    return consent, grant


@pytest.mark.django_db
def test_disclosure_previews_destination_and_minimum_fields_then_dual_audits(recruiter):
    application = ApplicationFactory(
        tenant=recruiter.tenant,
        opening__tenant=recruiter.tenant,
        active=True,
    )
    disclosure_consent_and_grant(
        application=application,
        recruiter=recruiter,
        fields=["name", "skills"],
    )
    preview = preview_disclosure(
        membership=recruiter,
        candidate_id=application.candidate_profile_id,
        values={
            "context_type": "APPLICATION",
            "context_id": application.id,
            "purpose": "HIRING_TEAM_SHARE",
            "destination": {
                "type": "HIRING_TEAM",
                "identifier": str(application.opening_id),
                "label": "Synthetic interview panel",
            },
            "requested_fields": ["name", "skills", "resume"],
        },
        request_key="synthetic-disclosure-preview",
    )
    assert preview.destination_preview == "Synthetic interview panel"
    assert preview.permitted_fields == ["name", "skills"]
    assert preview.excluded_fields == ["resume"]
    confirmed = confirm_disclosure(
        membership=recruiter,
        candidate_id=application.candidate_profile_id,
        preview_id=preview.id,
        preview_hash=preview.preview_hash,
        request_key="synthetic-disclosure-confirm",
    )
    assert confirmed.state == "PENDING"
    assert AuditEvent.objects.filter(action="CANDIDATE_DISCLOSURE_HISTORY").exists()
    assert AuditEvent.objects.filter(action="TENANT_CANDIDATE_DISCLOSURE").exists()
    assert str(application.opening_id) not in str(
        AuditEvent.objects.get(action="TENANT_CANDIDATE_DISCLOSURE").metadata
    )


@pytest.mark.django_db
def test_disclosure_rechecks_current_consent_and_reports_provider_failure(recruiter):
    application = ApplicationFactory(
        tenant=recruiter.tenant,
        opening__tenant=recruiter.tenant,
        active=True,
    )
    consent, _ = disclosure_consent_and_grant(
        application=application,
        recruiter=recruiter,
        fields=["name"],
    )
    preview = preview_disclosure(
        membership=recruiter,
        candidate_id=application.candidate_profile_id,
        values={
            "context_type": "APPLICATION",
            "context_id": application.id,
            "purpose": "HIRING_TEAM_SHARE",
            "destination": {
                "type": "HIRING_TEAM",
                "identifier": str(application.opening_id),
            },
            "requested_fields": ["name"],
        },
        request_key="synthetic-consent-preview",
    )
    consent.withdrawn_at = timezone.now()
    consent.save(update_fields=("withdrawn_at",))
    with pytest.raises(PermissionDenied):
        confirm_disclosure(
            membership=recruiter,
            candidate_id=application.candidate_profile_id,
            preview_id=preview.id,
            preview_hash=preview.preview_hash,
            request_key="synthetic-consent-confirm",
        )
    consent.withdrawn_at = None
    consent.save(update_fields=("withdrawn_at",))
    confirmed = confirm_disclosure(
        membership=recruiter,
        candidate_id=application.candidate_profile_id,
        preview_id=preview.id,
        preview_hash=preview.preview_hash,
        request_key="synthetic-consent-confirm-retry",
    )
    failed = record_disclosure_result(
        disclosure_id=confirmed.id,
        succeeded=False,
        result_category="PROVIDER_UNAVAILABLE",
    )
    assert failed.state == "FAILED"
    assert failed.result_category == "PROVIDER_UNAVAILABLE"


@pytest.mark.django_db
def test_cross_tenant_disclosure_is_non_enumerating(recruiter):
    application = ApplicationFactory(
        tenant=recruiter.tenant,
        opening__tenant=recruiter.tenant,
        active=True,
    )
    other_tenant = TenantFactory()
    outsider = MembershipFactory(tenant=other_tenant)
    with pytest.raises(PermissionDenied):
        preview_disclosure(
            membership=outsider,
            candidate_id=application.candidate_profile_id,
            values={
                "context_type": "APPLICATION",
                "context_id": application.id,
                "purpose": "HIRING_TEAM_SHARE",
                "destination": {"type": "HIRING_TEAM", "identifier": "synthetic"},
                "requested_fields": ["name"],
            },
            request_key="synthetic-cross-tenant",
        )
