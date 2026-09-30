import uuid
from datetime import timedelta
from typing import cast

import pytest
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from modules.audit.models import AuditEvent
from modules.candidate.models import CandidateSkill
from modules.privacy.export_service import download_export, expire_exports, generate_export
from modules.privacy.models import RightsExport
from modules.privacy.services import create_rights_request
from tests.factories import CandidateCapabilityFactory, make_candidate_profile, make_identity

pytestmark = pytest.mark.django_db


def test_export_contains_full_candidate_scope_and_expires_after_24_hours():
    profile = make_candidate_profile()
    CandidateSkill.objects.create(profile=profile, normalized_name="python", display_name="Python")
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    export = generate_export(request.export.id)
    assert export.state == RightsExport.State.READY
    assert export.expires_at is not None
    assert export.ready_at is not None
    assert export.expires_at - export.ready_at == timedelta(hours=24)
    payload = cast(dict[str, object], download_export(identity=profile.identity, request=request))
    profile_payload = cast(dict[str, object], payload["profile"])
    assert profile_payload["skills"] == ["Python"]
    assert export.object_key.startswith("rights-exports/")


def test_export_download_is_owner_only_and_partial_artifact_is_never_available():
    profile = make_candidate_profile()
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    with pytest.raises(ValidationError):
        download_export(identity=profile.identity, request=request)
    generate_export(request.export.id)
    with pytest.raises(PermissionDenied):
        download_export(identity=make_identity(), request=request)


def test_expired_export_is_erased_and_unavailable():
    profile = make_candidate_profile()
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    export = generate_export(request.export.id)
    export.expires_at = timezone.now() - timedelta(seconds=1)
    export.save(update_fields=("expires_at",))
    assert expire_exports() == 1
    export.refresh_from_db()
    assert export.payload_ciphertext is None and export.state == RightsExport.State.EXPIRED


def test_export_deadline_is_within_24_hours():
    profile = make_candidate_profile()
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    assert request.expected_completion_at <= request.submitted_at + timedelta(hours=24, seconds=1)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "candidate-export-rate-limit-test",
        }
    }
)
def test_export_download_is_rate_limited_and_audited():
    cache.clear()
    profile = make_candidate_profile()
    CandidateCapabilityFactory(identity=profile.identity, assigned_by=profile.identity)
    request = create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "EXPORT"}
    )
    generate_export(request.export.id)
    client = APIClient()
    client.force_authenticate(profile.identity)
    statuses = [
        client.post(
            f"/api/v1/candidate/rights-requests/{request.id}/download",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        ).status_code
        for _ in range(4)
    ]
    assert statuses == [200, 200, 200, 429]
    assert AuditEvent.objects.filter(action="RIGHTS_EXPORT_DOWNLOADED").count() == 3
