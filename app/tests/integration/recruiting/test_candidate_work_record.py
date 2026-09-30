import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.candidate.models import ConsentRecord, VisibilityRule
from modules.recruiting.candidate_work import (
    create_or_reuse_candidate_work,
    link_application_candidate_work,
)
from modules.recruiting.models import CandidateWorkRecord
from modules.search.models import SearchDefinition, SearchResultSnapshot
from tests.factories import ApplicationFactory


def sourced_context(*, profile, recruiter, opening=None):
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
    search = SearchDefinition.objects.create(
        tenant_id=recruiter.tenant_id,
        actor=recruiter.identity,
        context_type="AD_HOC",
        criteria_context={"type": "AD_HOC"},
        result_limit=25,
    )
    SearchResultSnapshot.objects.create(
        search=search,
        candidate_profile_id=profile.id,
        ordinal=1,
        score="1.000",
    )
    return search


@pytest.mark.django_db
@pytest.mark.parametrize("trigger", ["VIEW", "NOTE", "SHORTLIST", "STATUS_CHANGE"])
def test_first_context_action_creates_and_reuses_one_candidate_work(
    profile_factory, recruiter, trigger
):
    profile = profile_factory(published=True)
    search = sourced_context(profile=profile, recruiter=recruiter)
    first, created = create_or_reuse_candidate_work(
        membership=recruiter,
        candidate_id=profile.id,
        originating_search_id=search.id,
        trigger=trigger,
    )
    second, reused = create_or_reuse_candidate_work(
        membership=recruiter,
        candidate_id=profile.id,
        originating_search_id=search.id,
        trigger=trigger,
    )
    assert created is True
    assert reused is False
    assert first.id == second.id
    assert first.opening_id is None
    assert CandidateWorkRecord.objects.count() == 1


@pytest.mark.django_db
def test_later_application_links_without_overwriting_candidate_work(profile_factory, recruiter):
    profile = profile_factory(published=True)
    search = sourced_context(profile=profile, recruiter=recruiter)
    work, _ = create_or_reuse_candidate_work(
        membership=recruiter,
        candidate_id=profile.id,
        originating_search_id=search.id,
        trigger="NOTE",
    )
    work.internal_status = "CONTACTED"
    work.structured_reasons = ["SYNTHETIC_CONTEXT"]
    work.save()
    application = ApplicationFactory(
        tenant=recruiter.tenant,
        opening__tenant=recruiter.tenant,
        candidate_profile_id=profile.id,
        internal_status="SCREENING",
    )
    linked = link_application_candidate_work(application)
    application.refresh_from_db()
    work.refresh_from_db()
    assert linked == work
    assert application.candidate_work_record_id == work.id
    assert application.internal_status == "SCREENING"
    assert work.internal_status == "CONTACTED"
    assert work.structured_reasons == ["SYNTHETIC_CONTEXT"]
