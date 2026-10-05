from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules.search.views import _result


def test_result_history_requires_employment_consent_and_confirmed_dates():
    record = SimpleNamespace(
        company="Example",
        role_title="Engineer",
        start_date="2020-01-01",
        end_date="2021-01-01",
        start_date_state="CONFIRMED",
        end_date_state="SUGGESTED",
        is_current=False,
        employment_type="PERMANENT",
        provenance="CANDIDATE_REPORTED",
    )
    profile = SimpleNamespace(
        id="candidate",
        full_name_ciphertext=None,
        headline="Engineer",
        meaningful_work="Built backend services",
        current_role="Engineer",
        current_company="Example",
        location={},
        experience_years=2,
        skills=Mock(),
        work_arrangements=[],
        availability_date=None,
        notice_period="30 days",
        employment_history=Mock(),
    )
    profile.skills.values_list.return_value = ["Python"]
    profile.employment_history.all.return_value = [record]
    matched = SimpleNamespace(score=1, evidence=[], unknowns=[])
    membership = SimpleNamespace(tenant_id="tenant")
    with (
        patch("modules.search.views.consent_allows_findings", return_value=False),
        patch("modules.search.views.authorized_findings", return_value=[]),
    ):
        assert _result(profile, matched, membership)["summary"]["employment_history"] == []
        profile.employment_history.all.assert_not_called()
    with (
        patch("modules.search.views.consent_allows_findings", return_value=True),
        patch("modules.search.views.authorized_findings", return_value=[]),
    ):
        history = _result(profile, matched, membership)["summary"]["employment_history"]
        assert history[0]["company"] == "Example"
        assert history[0]["start_date"] == "2020-01-01"
        assert history[0]["end_date"] is None
