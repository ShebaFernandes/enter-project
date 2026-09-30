import pytest
from django.core.exceptions import ValidationError

from modules.operations.concurrency import strong_etag
from modules.recruiting.status_service import update_candidate_work
from tests.integration.recruiting.test_candidate_work_record import sourced_context


@pytest.mark.django_db
def test_not_relevant_requires_feedback_and_cancel_keeps_prior_state(profile_factory, recruiter):
    from modules.recruiting.candidate_work import create_or_reuse_candidate_work

    profile = profile_factory(published=True)
    search = sourced_context(profile=profile, recruiter=recruiter)
    work, _ = create_or_reuse_candidate_work(
        membership=recruiter,
        candidate_id=profile.id,
        originating_search_id=search.id,
        trigger="STATUS_CHANGE",
    )
    with pytest.raises(ValidationError):
        update_candidate_work(
            membership=recruiter,
            record=work,
            if_match=strong_etag(work.id, work.version),
            request_key="synthetic-not-relevant-empty",
            internal_status="NOT_RELEVANT",
            structured_reasons=[],
            explanatory_note="",
        )
    work.refresh_from_db()
    assert work.internal_status == "SOURCED"
    updated = update_candidate_work(
        membership=recruiter,
        record=work,
        if_match=strong_etag(work.id, work.version),
        request_key="synthetic-not-relevant-reason",
        internal_status="NOT_RELEVANT",
        structured_reasons=["ROLE_REQUIREMENTS_MISMATCH"],
    )
    assert updated.internal_status == "NOT_RELEVANT"
