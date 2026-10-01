import pytest

from modules.recruiting.comparison import compare_candidates
from modules.recruiting.models import (
    Application,
    CandidateWorkRecord,
    RecruitingStatusEvent,
    ShortlistEntry,
)
from tests.contract.test_comparison_api import comparison_profile, comparison_search


@pytest.mark.django_db
def test_comparison_is_read_only_and_has_no_automated_decision_output(recruiter, profile_factory):
    profiles = [
        comparison_profile(
            profile_factory=profile_factory,
            recruiter=recruiter,
            name_suffix=str(index),
        )
        for index in range(2)
    ]
    search = comparison_search(recruiter=recruiter, profiles=profiles)
    before = {
        "applications": Application.objects.count(),
        "candidate_work": CandidateWorkRecord.objects.count(),
        "shortlists": ShortlistEntry.objects.count(),
        "statuses": RecruitingStatusEvent.objects.count(),
    }

    result = compare_candidates(
        membership=recruiter,
        candidate_ids=[profile.id for profile in profiles],
        context_type="SEARCH",
        context_id=search.id,
    )

    assert before == {
        "applications": Application.objects.count(),
        "candidate_work": CandidateWorkRecord.objects.count(),
        "shortlists": ShortlistEntry.objects.count(),
        "statuses": RecruitingStatusEvent.objects.count(),
    }
    rendered = str(result).casefold()
    for prohibited in (
        "recommendation",
        "recommended",
        "best candidate",
        "reject",
        "contact",
        "protected attribute",
        "score",
        "rank",
    ):
        assert prohibited not in rendered


@pytest.mark.django_db
def test_short_tenure_does_not_change_comparison_order_or_create_state(recruiter, profile_factory):
    with_finding = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="Finding"
    )
    without_finding = comparison_profile(
        profile_factory=profile_factory,
        recruiter=recruiter,
        name_suffix="NoFinding",
        complete=False,
    )
    search = comparison_search(recruiter=recruiter, profiles=[with_finding, without_finding])

    result = compare_candidates(
        membership=recruiter,
        candidate_ids=[without_finding.id, with_finding.id],
        context_type="SEARCH",
        context_id=search.id,
    )

    assert [item["candidate_id"] for item in result["candidates"]] == [
        str(without_finding.id),
        str(with_finding.id),
    ]
    assert result["candidates"][0]["findings"] == []
    assert result["candidates"][1]["findings"][0]["informational_only"] is True
