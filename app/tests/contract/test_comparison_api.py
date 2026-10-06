import uuid
from datetime import date, timedelta

import pytest
from django.utils import timezone

from modules.candidate.finding_evaluators import evaluate_employment_record
from modules.candidate.models import (
    CandidateSkill,
    ConsentRecord,
    EmploymentRecord,
    VisibilityRule,
)
from modules.search.models import SearchDefinition, SearchResultSnapshot


def comparison_profile(*, profile_factory, recruiter, name_suffix: str, complete: bool = True):
    profile = profile_factory(published=True)
    profile.headline = f"Engineer {name_suffix}"
    profile.notice_period = "30 days" if complete else ""
    profile.availability_date = date(2026, 11, 1) if complete else None
    profile.role_categories = ["software engineer"] if complete else []
    profile.preferred_locations = ["bengaluru"] if complete else []
    profile.work_arrangements = ["REMOTE"] if complete else []
    profile.save()
    CandidateSkill.objects.create(
        profile=profile,
        normalized_name=f"python-{name_suffix.casefold()}",
        display_name=f"Python {name_suffix}",
        provenance="CANDIDATE_REPORTED",
    )
    consent = ConsentRecord.objects.create(
        profile=profile,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile", "skills", "employment_history"],
        audience_scope={"approved_tenant_ids": [str(recruiter.tenant_id)]},
        notice_version="v1",
        affirmative_action="CHECKBOX",
        source_request_id=str(uuid.uuid4()),
        expires_at=timezone.now() + timedelta(days=30),
    )
    VisibilityRule.objects.create(
        profile=profile,
        mode="APPROVED_RECRUITERS",
        approved_tenant_ids=[str(recruiter.tenant_id)],
        consent_record=consent,
        actor=profile.identity,
    )
    employment = EmploymentRecord.objects.create(
        profile=profile,
        company=f"Synthetic Employer {name_suffix}",
        role_title="Engineer" if complete else "",
        start_date=date(2025, 1, 1) if complete else None,
        end_date=date(2025, 9, 1) if complete else None,
        start_date_state="CONFIRMED" if complete else "MISSING",
        end_date_state="CONFIRMED" if complete else "MISSING",
        start_date_precision="DAY" if complete else "UNKNOWN",
        end_date_precision="DAY" if complete else "UNKNOWN",
        is_current=False,
        employment_type="PERMANENT" if complete else "UNKNOWN",
        employment_type_state="CONFIRMED" if complete else "MISSING",
        provenance="CANDIDATE_REPORTED",
    )
    if complete:
        evaluate_employment_record(employment)
    return profile


def comparison_search(*, recruiter, profiles):
    search = SearchDefinition.objects.create(
        tenant=recruiter.tenant,
        actor=recruiter.identity,
        context_type="AD_HOC",
        criteria_context={"type": "AD_HOC"},
    )
    for ordinal, profile in enumerate(profiles, 1):
        SearchResultSnapshot.objects.create(
            search=search,
            candidate_profile_id=profile.id,
            ordinal=ordinal,
            score="1.000",
            evidence=[
                {
                    "evidence_id": str(uuid.uuid4()),
                    "label": "skill",
                    "provenance": "CANDIDATE_REPORTED",
                }
            ],
            unknowns=[] if ordinal == 1 else ["notice_period"],
        )
    return search


def opening_comparison_search(*, recruiter, opening, profiles):
    for profile in profiles:
        rule = profile.visibility_rules.get(superseded_at__isnull=True)
        rule.mode = "MATCHING_ROLES"
        rule.approved_tenant_ids = []
        rule.matching_preferences = {
            "role_categories": [opening.title.casefold()],
            "preferred_locations": ["bengaluru"],
            "work_arrangements": [opening.work_mode],
        }
        rule.save(update_fields=("mode", "approved_tenant_ids", "matching_preferences"))
    search = SearchDefinition.objects.create(
        tenant=recruiter.tenant,
        actor=recruiter.identity,
        context_type="OPENING",
        criteria_context={"type": "OPENING", "opening_id": str(opening.id)},
        derived_opening=opening,
    )
    for ordinal, profile in enumerate(profiles, 1):
        SearchResultSnapshot.objects.create(
            search=search,
            candidate_profile_id=profile.id,
            ordinal=ordinal,
            score="1.000",
            evidence=[],
            unknowns=[],
        )
    return search


def compare(api_client, recruiter, search, candidate_ids):
    return api_client.post(
        f"/api/v1/tenants/{recruiter.tenant_id}/comparisons",
        {
            "candidate_ids": [str(value) for value in candidate_ids],
            "context_type": "SEARCH",
            "context_id": str(search.id),
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"comparison-{uuid.uuid4()}",
    )


@pytest.mark.django_db
def test_comparison_returns_consistent_fields_stable_order_unknowns_and_findings(
    api_client, recruiter, profile_factory
):
    first = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="One"
    )
    second = comparison_profile(
        profile_factory=profile_factory,
        recruiter=recruiter,
        name_suffix="Two",
        complete=False,
    )
    search = comparison_search(recruiter=recruiter, profiles=[first, second])
    api_client.force_login(recruiter.identity)

    response = compare(api_client, recruiter, search, [second.id, first.id])

    assert response.status_code == 200
    assert response.data["fields"] == [
        "name",
        "current_role",
        "current_company",
        "location",
        "experience",
        "notice_or_availability",
        "compensation_availability",
        "skills",
        "employment",
        "education",
        "preferences",
        "match_evidence",
        "informational_findings",
    ]
    assert [item["candidate_id"] for item in response.data["candidates"]] == [
        str(second.id),
        str(first.id),
    ]
    for item in response.data["candidates"]:
        assert list(item["permitted_fields"]) == response.data["fields"]
        assert "score" not in str(item).casefold()
        assert "recommendation" not in str(item).casefold()
        assert "best candidate" not in str(item).casefold()
    assert response.data["candidates"][0]["permitted_fields"]["employment"]["state"] == "UNKNOWN"
    assert "employment" in response.data["candidates"][0]["unknowns"]
    finding = response.data["candidates"][1]["findings"][0]
    assert finding["code"] == "SHORT_TENURE"
    assert finding["informational_only"] is True


@pytest.mark.django_db
def test_comparison_validates_selection_limits_and_duplicates(
    api_client, recruiter, profile_factory
):
    profiles = [
        comparison_profile(
            profile_factory=profile_factory,
            recruiter=recruiter,
            name_suffix=str(index),
        )
        for index in range(11)
    ]
    search = comparison_search(recruiter=recruiter, profiles=profiles)
    api_client.force_login(recruiter.identity)

    assert compare(api_client, recruiter, search, [profiles[0].id]).status_code == 422
    assert (
        compare(api_client, recruiter, search, [profiles[0].id, profiles[0].id]).status_code == 422
    )
    assert compare(api_client, recruiter, search, [item.id for item in profiles]).status_code == 422


@pytest.mark.django_db
def test_comparison_omits_candidate_that_became_ineligible_after_selection(
    api_client, recruiter, profile_factory
):
    first = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="Visible"
    )
    second = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="Hidden"
    )
    search = comparison_search(recruiter=recruiter, profiles=[first, second])
    second.profile_state = "HIDDEN"
    second.save(update_fields=("profile_state",))
    api_client.force_login(recruiter.identity)

    response = compare(api_client, recruiter, search, [first.id, second.id])

    assert response.status_code == 200
    assert [item["candidate_id"] for item in response.data["candidates"]] == [str(first.id)]


@pytest.mark.django_db
def test_comparison_uses_only_current_audience_consent_field_scope(
    api_client, recruiter, profile_factory
):
    profile = comparison_profile(
        profile_factory=profile_factory,
        recruiter=recruiter,
        name_suffix="Scoped",
    )
    current_rule = profile.visibility_rules.get(superseded_at__isnull=True)
    current_rule.consent_record.field_scope = ["profile"]
    current_rule.consent_record.save(update_fields=("field_scope",))
    ConsentRecord.objects.create(
        profile=profile,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile", "skills", "employment_history"],
        audience_scope={"approved_tenant_ids": [str(uuid.uuid4())]},
        notice_version="v1",
        affirmative_action="CHECKBOX",
        source_request_id=str(uuid.uuid4()),
        expires_at=timezone.now() + timedelta(days=30),
    )
    second = comparison_profile(
        profile_factory=profile_factory,
        recruiter=recruiter,
        name_suffix="Second",
    )
    search = comparison_search(recruiter=recruiter, profiles=[profile, second])
    api_client.force_login(recruiter.identity)

    response = compare(api_client, recruiter, search, [profile.id, second.id])

    assert response.status_code == 200
    scoped = response.data["candidates"][0]["permitted_fields"]
    assert scoped["skills"] == {"state": "UNAVAILABLE", "value": None, "provenance": []}
    assert scoped["employment"] == {
        "state": "UNAVAILABLE",
        "value": None,
        "provenance": [],
    }
    assert scoped["match_evidence"] == {
        "state": "UNKNOWN",
        "value": None,
        "provenance": [],
    }


@pytest.mark.django_db
def test_comparison_denies_cross_tenant_or_unowned_search_context(
    api_client, recruiter, profile_factory
):
    from tests.factories import MembershipFactory, TenantFactory

    first = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="One"
    )
    second = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="Two"
    )
    search = comparison_search(recruiter=recruiter, profiles=[first, second])
    outsider = MembershipFactory(tenant=TenantFactory())
    api_client.force_login(outsider.identity)

    response = api_client.post(
        f"/api/v1/tenants/{outsider.tenant_id}/comparisons",
        {
            "candidate_ids": [str(first.id), str(second.id)],
            "context_type": "SEARCH",
            "context_id": str(search.id),
        },
        format="json",
        HTTP_X_TENANT_ID=str(outsider.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"comparison-{uuid.uuid4()}",
    )
    assert response.status_code in {403, 404}
    assert "candidate" not in str(response.data).casefold()


@pytest.mark.django_db
def test_opening_comparison_enforces_current_opening_and_hiring_team_scope(
    api_client, recruiter, profile_factory, opening_factory
):
    from tests.factories import MembershipFactory

    opening = opening_factory(tenant=recruiter.tenant)
    profiles = [
        comparison_profile(
            profile_factory=profile_factory,
            recruiter=recruiter,
            name_suffix=f"Opening-{index}",
        )
        for index in range(2)
    ]
    opening_comparison_search(recruiter=recruiter, opening=opening, profiles=profiles)
    api_client.force_login(recruiter.identity)
    allowed = api_client.post(
        f"/api/v1/tenants/{recruiter.tenant_id}/comparisons",
        {
            "candidate_ids": [str(profile.id) for profile in profiles],
            "context_type": "OPENING",
            "context_id": str(opening.id),
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"comparison-{uuid.uuid4()}",
    )
    assert allowed.status_code == 200
    assert len(allowed.data["candidates"]) == 2

    hiring_manager = MembershipFactory(
        tenant=recruiter.tenant,
        hiring_manager=True,
        scope={"opening_ids": [str(opening.id)]},
    )
    api_client.force_login(hiring_manager.identity)
    denied = api_client.post(
        f"/api/v1/tenants/{recruiter.tenant_id}/comparisons",
        {
            "candidate_ids": [str(profile.id) for profile in profiles],
            "context_type": "OPENING",
            "context_id": str(opening.id),
        },
        format="json",
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
        HTTP_IDEMPOTENCY_KEY=f"comparison-{uuid.uuid4()}",
    )
    assert denied.status_code == 404
