from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.candidate.models import CandidateProfile, EmploymentRecord
from modules.identity.models import SessionCredential, StepUpEvidence
from modules.operations.crypto import encrypt
from modules.privacy.deletion_service import (
    complete_due_deletion,
    create_active_process_exception,
    resolve_exception,
)
from modules.privacy.models import (
    ActiveProcessRetentionException,
    DataRightsRequest,
    DeletionLedger,
    LegalHold,
)
from modules.privacy.services import create_rights_request
from tests.factories import (
    ApplicationFactory,
    CandidateProfileFactory,
    EmploymentRecordFactory,
    IdentityFactory,
)

pytestmark = pytest.mark.django_db


def step_up(identity):
    now = timezone.now()
    session = SessionCredential.objects.create(
        identity=identity,
        session_key_hash=b"deletion-session-" + identity.id.bytes,
        provider="COGNITO",
        assurance=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        authenticated_at=now,
        expires_at=now + timedelta(hours=1),
    )
    return StepUpEvidence.objects.create(
        identity=identity,
        session_credential=session,
        purpose="candidate-deletion",
        method=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        nonce_hash=b"deletion-nonce-" + identity.id.bytes,
        verified_at=now,
        expires_at=now + timedelta(minutes=10),
    )


def test_deletion_requires_step_up_and_confirmation():
    profile = CandidateProfileFactory()
    with pytest.raises(ValidationError):
        create_rights_request(
            identity=profile.identity,
            profile=profile,
            values={"request_type": "DELETE", "confirm_consequences": True},
        )


def test_confirmed_deletion_hides_immediately_and_completes_with_ledger():
    profile = CandidateProfileFactory(profile_state=CandidateProfile.State.PUBLISHED)
    EmploymentRecordFactory(profile=profile)
    evidence = step_up(profile.identity)
    request = create_rights_request(
        identity=profile.identity,
        profile=profile,
        values={"request_type": "DELETE", "confirm_consequences": True},
        step_up_evidence=evidence,
    )
    profile.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.DELETION_PENDING
    assert request.expected_completion_at <= request.submitted_at + timedelta(days=30, seconds=1)
    assert complete_due_deletion(request.id, force_due=True)
    profile.refresh_from_db()
    request.refresh_from_db()
    assert profile.profile_state == CandidateProfile.State.DELETED
    assert not EmploymentRecord.objects.filter(profile=profile).exists()
    assert request.state == DataRightsRequest.State.COMPLETED
    ledger = DeletionLedger.objects.get()
    assert ledger.subject_token and str(profile.identity_id).encode() not in ledger.subject_token
    assert ledger.evidence_hash and ledger.replay_status == "PENDING"


def test_active_process_exception_has_exact_versioned_fields_and_holds_only_scope():
    profile = CandidateProfileFactory()
    application = ApplicationFactory(candidate_profile_id=profile.id, active=True)
    exception = create_active_process_exception(
        profile=profile,
        application=application,
        policy_version="retention-v1",
        legal_basis="Active hiring process",
        retained_data_scope=["application.answers"],
        review_date=timezone.now() + timedelta(days=30),
        terminating_event="APPLICATION_CLOSED",
        approved_by=IdentityFactory(),
        audit_references=[str(profile.id)],
    )
    assert exception.version == 1 and exception.lifecycle_state == "ACTIVE"
    resolved = resolve_exception(item=exception, actor=exception.approved_by)
    assert resolved.lifecycle_state == ActiveProcessRetentionException.State.RESOLVED
    assert resolved.resolution_date and resolved.version == 2


def test_exception_application_must_reference_same_candidate():
    profile = CandidateProfileFactory()
    with pytest.raises(ValidationError):
        create_active_process_exception(
            profile=profile,
            application=ApplicationFactory(),
            policy_version="retention-v1",
            legal_basis="Active process",
            retained_data_scope=["application"],
            review_date=timezone.now() + timedelta(days=30),
            terminating_event="APPLICATION_CLOSED",
            approved_by=IdentityFactory(),
            audit_references=[str(profile.id)],
        )


def test_terminating_event_resolution_resumes_held_deletion():
    profile = CandidateProfileFactory(profile_state=CandidateProfile.State.PUBLISHED)
    exception = create_active_process_exception(
        profile=profile,
        application=ApplicationFactory(candidate_profile_id=profile.id, active=True),
        policy_version="retention-v1",
        legal_basis="Active hiring process",
        retained_data_scope=["application.answers"],
        review_date=timezone.now() + timedelta(days=30),
        terminating_event="APPLICATION_CLOSED",
        approved_by=IdentityFactory(),
        audit_references=[str(profile.id)],
    )
    request = create_rights_request(
        identity=profile.identity,
        profile=profile,
        values={"request_type": "DELETE", "confirm_consequences": True},
        step_up_evidence=step_up(profile.identity),
    )
    assert not complete_due_deletion(request.id, force_due=True)
    resolve_exception(item=exception, actor=exception.approved_by)
    request.refresh_from_db()
    profile.refresh_from_db()
    assert request.state == DataRightsRequest.State.COMPLETED
    assert profile.profile_state == CandidateProfile.State.DELETED


def test_active_legal_hold_prevents_erasure_but_keeps_profile_hidden():
    profile = CandidateProfileFactory(profile_state=CandidateProfile.State.PUBLISHED)
    evidence = step_up(profile.identity)
    request = create_rights_request(
        identity=profile.identity,
        profile=profile,
        values={"request_type": "DELETE", "confirm_consequences": True},
        step_up_evidence=evidence,
    )
    LegalHold.objects.create(
        profile=profile,
        scope=["employment_history"],
        authority_reference="SYNTHETIC-HOLD-001",
        approver=IdentityFactory(),
        encrypted_rationale=encrypt("Synthetic litigation hold"),
        starts_at=timezone.now(),
        review_at=timezone.now() + timedelta(days=30),
    )
    assert not complete_due_deletion(request.id, force_due=True)
    request.refresh_from_db()
    profile.refresh_from_db()
    assert request.state == DataRightsRequest.State.HELD
    assert profile.profile_state == CandidateProfile.State.DELETION_PENDING
