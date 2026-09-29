from __future__ import annotations

from datetime import timedelta
from typing import cast

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.candidate.models import CandidateProfile
from modules.candidate.serializers import CandidateProfilePatchSerializer
from modules.candidate.services import profile_data, update_profile
from modules.candidate.visibility import withdraw_consent
from modules.operations.concurrency import strong_etag
from modules.operations.crypto import encrypt

from .audit import audit_rights_action
from .models import DataRightsRequest, RightsEscalation


def rights_request_data(item: DataRightsRequest) -> dict[str, object]:
    exceptions = []
    for exception in item.profile.retention_exceptions.filter(
        lifecycle_state__in=["ACTIVE", "UNDER_REVIEW"]
    ):
        exceptions.append(
            {
                "id": exception.id,
                "version": exception.version,
                "candidate_id": exception.profile_id,
                "application_id": exception.application_id,
                "policy_version": exception.policy_version,
                "legal_basis": exception.legal_basis,
                "retained_data_scope": exception.retained_data_scope,
                "lifecycle_state": exception.lifecycle_state,
                "start_date": exception.start_date,
                "review_date": exception.review_date,
                "terminating_event": exception.terminating_event,
                "resolution_date": exception.resolution_date,
                "approver_id": exception.approved_by_id,
                "audit_references": exception.audit_references,
            }
        )
    return {
        "id": item.id,
        "request_type": item.request_type,
        "state": item.state,
        "scope": item.scope,
        "submitted_at": item.submitted_at,
        "expected_completion_at": item.expected_completion_at,
        "completed_at": item.completed_at,
        "safe_detail": item.safe_detail or None,
        "exception_scope": exceptions[0]["retained_data_scope"] if exceptions else None,
        "active_process_exceptions": exceptions,
        "support_escalation_available": item.state
        in {
            DataRightsRequest.State.FAILED,
            DataRightsRequest.State.HELD,
        }
        or item.expected_completion_at <= timezone.now(),
    }


@transaction.atomic
def create_rights_request(
    *, identity, profile: CandidateProfile, values: dict[str, object], step_up_evidence=None
) -> DataRightsRequest:
    if profile.identity_id != identity.id:
        raise PermissionDenied("Rights request unavailable")
    request_type = str(values["request_type"])
    now = timezone.now()
    immediate = request_type in {
        DataRightsRequest.RequestType.ACCESS,
        DataRightsRequest.RequestType.CORRECTION,
        DataRightsRequest.RequestType.WITHDRAW_CONSENT,
        DataRightsRequest.RequestType.HIDE_PROFILE,
    }
    expected = now
    if request_type == DataRightsRequest.RequestType.EXPORT:
        expected = now + timedelta(hours=24)
    elif request_type == DataRightsRequest.RequestType.DELETE:
        expected = now + timedelta(days=30)
        if step_up_evidence is None or values.get("confirm_consequences") is not True:
            raise ValidationError(
                {"deletion": "Recent step-up and consequence confirmation are required."}
            )
    item = DataRightsRequest.objects.create(
        profile=profile,
        request_type=request_type,
        state=DataRightsRequest.State.COMPLETED if immediate else DataRightsRequest.State.PENDING,
        scope=values.get("scope", {}),
        correction=values.get("correction", {}),
        step_up_evidence_id=getattr(step_up_evidence, "id", None),
        consequence_confirmed_at=now if request_type == "DELETE" else None,
        expected_completion_at=expected,
        completed_at=now if immediate else None,
        safe_detail="Completed immediately" if immediate else "Request accepted",
    )
    if request_type == DataRightsRequest.RequestType.CORRECTION:
        correction = cast(dict[str, object], values.get("correction", {}))
        if not correction:
            raise ValidationError({"correction": "At least one correction is required."})
        correction_serializer = CandidateProfilePatchSerializer(data=correction, partial=True)
        correction_serializer.is_valid(raise_exception=True)
        update_profile(
            identity=identity,
            if_match=strong_etag(profile.id, profile.version),
            values=dict(correction_serializer.validated_data),
        )
    elif request_type == DataRightsRequest.RequestType.WITHDRAW_CONSENT:
        withdraw_consent(identity=identity, profile=profile)
    elif request_type == DataRightsRequest.RequestType.HIDE_PROFILE:
        profile.profile_state = CandidateProfile.State.HIDDEN
        profile.version += 1
        profile.save(update_fields=("profile_state", "version", "updated_at"))
    elif request_type == DataRightsRequest.RequestType.EXPORT:
        from .models import RightsExport

        RightsExport.objects.create(request=item)
    elif request_type == DataRightsRequest.RequestType.DELETE:
        from .deletion_service import begin_deletion

        begin_deletion(identity=identity, profile=profile, request=item)
    audit_rights_action(actor=identity, request=item, action="RIGHTS_REQUEST_CREATED")
    return item


def access_snapshot(*, identity, profile: CandidateProfile) -> dict[str, object]:
    if profile.identity_id != identity.id:
        raise PermissionDenied("Profile unavailable")
    return profile_data(profile)


@transaction.atomic
def escalate(*, identity, item: DataRightsRequest, reason: str) -> RightsEscalation:
    if item.profile.identity_id != identity.id:
        raise PermissionDenied("Rights request unavailable")
    if not reason.strip():
        raise ValidationError({"reason": "A reason is required."})
    escalation = RightsEscalation.objects.create(
        request=item, reason_ciphertext=encrypt(reason.strip())
    )
    item.support_escalated_at = timezone.now()
    item.save(update_fields=("support_escalated_at",))
    audit_rights_action(actor=identity, request=item, action="RIGHTS_REQUEST_ESCALATED")
    return escalation
