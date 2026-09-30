import uuid

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from modules.candidate.models import ConsentRecord, VisibilityRule
from modules.search.eligibility import validate_search_context


@pytest.mark.django_db
def test_context_enforces_active_opening_and_tenant(tenant, recruiter, opening_factory):
    opening = opening_factory(tenant=tenant, state="OPEN")
    selected_opening = validate_search_context(
        {"type": "OPENING", "opening_id": str(opening.id)}, recruiter
    )
    assert selected_opening is not None
    assert selected_opening.id == opening.id
    with pytest.raises(ValidationError):
        validate_search_context({"type": "AD_HOC", "opening_id": str(opening.id)}, recruiter)
    opening.state = "CLOSED"
    opening.save(update_fields=["state"])
    with pytest.raises(PermissionDenied):
        validate_search_context({"type": "OPENING", "opening_id": str(opening.id)}, recruiter)


@pytest.mark.django_db
def test_ad_hoc_requires_explicit_audience(profile_factory, tenant, recruiter):
    profile = profile_factory(published=True)
    consent = ConsentRecord.objects.create(
        profile=profile,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile", "employment_history"],
        audience_scope={"approved_tenant_ids": [str(tenant.id)]},
        notice_version="v1",
        affirmative_action="CHECKBOX",
        source_request_id=str(uuid.uuid4()),
        expires_at=__import__("django").utils.timezone.now()
        + __import__("datetime").timedelta(days=30),
    )
    VisibilityRule.objects.create(
        profile=profile,
        mode="APPROVED_RECRUITERS",
        approved_tenant_ids=[str(tenant.id)],
        consent_record=consent,
        actor=profile.identity,
    )
    from modules.search.eligibility import eligible_profiles

    assert list(eligible_profiles(recruiter, {"type": "AD_HOC"}).values_list("id", flat=True)) == [
        profile.id
    ]
    with pytest.raises(PermissionDenied):
        eligible_profiles(recruiter, {"type": "OPENING", "opening_id": str(uuid.uuid4())})


@pytest.mark.django_db
def test_ad_hoc_requires_both_visibility_and_consent_audience(profile_factory, tenant, recruiter):
    profile = profile_factory(published=True)
    consent = ConsentRecord.objects.create(
        profile=profile,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile"],
        audience_scope={"approved_tenant_ids": []},
        notice_version="v1",
        affirmative_action="CHECKBOX",
        source_request_id=str(uuid.uuid4()),
        expires_at=__import__("django").utils.timezone.now()
        + __import__("datetime").timedelta(days=30),
    )
    VisibilityRule.objects.create(
        profile=profile,
        mode="APPROVED_RECRUITERS",
        approved_tenant_ids=[str(tenant.id)],
        consent_record=consent,
        actor=profile.identity,
    )
    from modules.search.eligibility import eligible_profiles

    assert not eligible_profiles(recruiter, {"type": "AD_HOC"}).exists()


@pytest.mark.django_db
def test_opening_matching_is_deterministic_and_other_visibility_modes_are_excluded(
    profile_factory, tenant, recruiter, opening_factory
):
    from modules.search.eligibility import eligible_profiles

    opening = opening_factory(tenant=tenant)
    matching = profile_factory(published=True)
    consent = ConsentRecord.objects.create(
        profile=matching,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile"],
        audience_scope={"matching_preferences": True},
        notice_version="v1",
        affirmative_action="CHECKBOX",
        source_request_id=str(uuid.uuid4()),
        expires_at=__import__("django").utils.timezone.now()
        + __import__("datetime").timedelta(days=30),
    )
    VisibilityRule.objects.create(
        profile=matching,
        mode="MATCHING_ROLES",
        matching_preferences={
            "role_categories": ["software engineer"],
            "preferred_locations": ["bengaluru"],
            "work_arrangements": ["REMOTE"],
        },
        consent_record=consent,
        actor=matching.identity,
    )
    assert list(
        eligible_profiles(
            recruiter, {"type": "OPENING", "opening_id": str(opening.id)}
        ).values_list("id", flat=True)
    ) == [matching.id]
    assert not eligible_profiles(recruiter, {"type": "AD_HOC"}).filter(pk=matching.id).exists()

    matching.visibility_rules.update(mode="NOT_LOOKING")
    assert not eligible_profiles(
        recruiter, {"type": "OPENING", "opening_id": str(opening.id)}
    ).exists()
