import pytest

from modules.audit.models import AuditEvent
from modules.candidate.services import update_profile
from modules.operations.concurrency import strong_etag
from modules.privacy.services import create_rights_request
from tests.factories import CandidateProfileFactory

pytestmark = [pytest.mark.django_db, pytest.mark.security]


def test_candidate_profile_and_rights_audit_are_value_minimized():
    profile = CandidateProfileFactory()
    update_profile(
        identity=profile.identity,
        if_match=strong_etag(profile.id, profile.version),
        values={"full_name": "Sensitive Synthetic Name"},
    )
    create_rights_request(
        identity=profile.identity, profile=profile, values={"request_type": "ACCESS"}
    )
    events = list(AuditEvent.objects.values("action", "metadata"))
    assert {event["action"] for event in events} >= {
        "CANDIDATE_PROFILE_UPDATE",
        "RIGHTS_REQUEST_CREATED",
    }
    assert "Sensitive Synthetic Name" not in str(events)
