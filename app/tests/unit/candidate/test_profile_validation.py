from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from modules.candidate.models import CandidateProfile
from modules.candidate.serializers import CandidateProfilePatchSerializer
from tests.factories import CandidateProfileFactory

pytestmark = pytest.mark.django_db


def test_profile_accepts_zero_and_fractional_experience_but_rejects_negative():
    profile = CandidateProfileFactory(experience_years=Decimal("0.25"))
    profile.full_clean()
    profile.experience_years = Decimal("-0.01")
    with pytest.raises(ValidationError):
        profile.full_clean()


@pytest.mark.parametrize("value", ["", " "])
def test_required_profile_text_rejects_blank(value):
    serializer = CandidateProfilePatchSerializer(data={"full_name": value})
    assert not serializer.is_valid()


def test_compensation_requires_currency_minor_amount_and_period():
    valid = CandidateProfilePatchSerializer(
        data={"compensation": {"currency": "INR", "amount_minor": 100_000, "period": "MONTH"}}
    )
    assert valid.is_valid(), valid.errors
    invalid = CandidateProfilePatchSerializer(data={"compensation": {"currency": "inr"}})
    assert not invalid.is_valid()


def test_optional_fields_safe_links_and_narrative_limit():
    serializer = CandidateProfilePatchSerializer(
        data={
            "professional_links": ["https://example.invalid/profile"],
            "meaningful_work": "x" * 300,
        }
    )
    assert serializer.is_valid(), serializer.errors
    bad = CandidateProfilePatchSerializer(
        data={"professional_links": ["ftp://example.invalid/file"], "meaningful_work": "x" * 301}
    )
    assert not bad.is_valid()


def test_profile_identity_is_unique():
    profile = CandidateProfileFactory()
    with pytest.raises(IntegrityError):
        CandidateProfile.objects.create(identity=profile.identity)
