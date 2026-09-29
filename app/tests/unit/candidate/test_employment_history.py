from datetime import date

import pytest

from modules.candidate.models import EmploymentRecord
from modules.candidate.serializers import EmploymentRecordInputSerializer
from modules.candidate.services import update_profile
from modules.operations.concurrency import strong_etag
from modules.operations.models import OutboxEvent
from tests.factories import EmploymentRecordFactory

pytestmark = pytest.mark.django_db


def payload(**overrides):
    values = {
        "company": "Synthetic Company",
        "role_title": "Engineer",
        "start_date": "2025-01-01",
        "end_date": "2025-09-01",
        "start_date_state": "CONFIRMED",
        "end_date_state": "CONFIRMED",
        "is_current": False,
        "employment_type": "PERMANENT",
        "employment_type_state": "CONFIRMED",
        "provenance": "CANDIDATE_REPORTED",
        "source_spans": [],
    }
    values.update(overrides)
    return values


def test_missing_and_ambiguous_dates_are_safe_and_not_invented():
    serializer = EmploymentRecordInputSerializer(
        data=payload(
            start_date=None, end_date=None, start_date_state="AMBIGUOUS", end_date_state="MISSING"
        )
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["start_date"] is None
    assert "reason_for_leaving" not in serializer.fields


def test_confirmed_missing_date_and_current_role_end_date_are_rejected():
    assert not EmploymentRecordInputSerializer(data=payload(start_date=None)).is_valid()
    assert not EmploymentRecordInputSerializer(data=payload(is_current=True)).is_valid()


@pytest.mark.parametrize(
    "employment_type",
    [
        "PERMANENT",
        "INTERNSHIP",
        "APPRENTICESHIP",
        "FIXED_TERM_CONTRACT",
        "CONSULTING",
        "SEASONAL",
        "OTHER_TEMPORARY",
        "OTHER",
        "UNKNOWN",
    ],
)
def test_employment_type_vocabulary(employment_type):
    serializer = EmploymentRecordInputSerializer(data=payload(employment_type=employment_type))
    assert serializer.is_valid(), serializer.errors


def test_correction_preserves_stable_id_versions_and_emits_recalculation_boundary():
    record = EmploymentRecordFactory()
    profile = record.profile
    values = payload(id=str(record.id), end_date="2026-01-01")
    serializer = EmploymentRecordInputSerializer(data=values)
    assert serializer.is_valid(), serializer.errors
    update_profile(
        identity=profile.identity,
        if_match=strong_etag(profile.id, profile.version),
        values={"employment_history": [dict(serializer.validated_data)]},
    )
    record.refresh_from_db()
    assert record.id
    assert record.end_date == date(2026, 1, 1)
    assert record.start_date_precision == EmploymentRecord.DatePrecision.DAY
    assert record.end_date_precision == EmploymentRecord.DatePrecision.DAY
    assert record.version == 2
    event = OutboxEvent.objects.get(event_type="profile.employment_history_changed.v1")
    assert event.payload["records"][0]["record_id"] == str(record.id)
    assert "company" not in event.payload and "end_date" not in event.payload
