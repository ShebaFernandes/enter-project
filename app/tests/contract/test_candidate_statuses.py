import pytest

from modules.recruiting.statuses import candidate_status_suggestion


@pytest.mark.parametrize(
    ("internal", "candidate"),
    [
        ("SOURCED", None),
        ("SHORTLISTED", "SHORTLISTED"),
        ("CONTACTED", "RECRUITER_INTERESTED"),
        ("SCREENING", "RECRUITER_INTERESTED"),
        ("INTERVIEWING", "INTERVIEW_REQUESTED"),
        ("OFFERED", "OFFER_MADE"),
        ("REJECTED", "NOT_SELECTED"),
        ("NOT_RELEVANT", None),
        ("HIRED", None),
    ],
)
def test_internal_status_mapping_is_nullable_and_canonical(internal, candidate):
    assert candidate_status_suggestion(internal) == candidate


def test_unknown_internal_status_is_rejected():
    with pytest.raises(ValueError):
        candidate_status_suggestion("AUTOMATICALLY_REJECTED")
