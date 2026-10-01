import pytest

from modules.recruiting.comparison import compare_candidates
from tests.contract.test_comparison_api import comparison_profile, comparison_search


@pytest.mark.postgres
@pytest.mark.django_db
def test_comparison_reauthorizes_visibility_at_read_time(recruiter, profile_factory):
    visible = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="Visible"
    )
    withdrawn = comparison_profile(
        profile_factory=profile_factory, recruiter=recruiter, name_suffix="Withdrawn"
    )
    search = comparison_search(recruiter=recruiter, profiles=[visible, withdrawn])
    consent = withdrawn.consents.get(purpose="RECRUITING_DISCOVERY")
    consent.withdrawn_at = consent.expires_at
    consent.save(update_fields=("withdrawn_at",))

    result = compare_candidates(
        membership=recruiter,
        candidate_ids=[visible.id, withdrawn.id],
        context_type="SEARCH",
        context_id=search.id,
    )

    assert [item["candidate_id"] for item in result["candidates"]] == [str(visible.id)]
