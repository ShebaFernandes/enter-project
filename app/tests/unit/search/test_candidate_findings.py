from datetime import date
from decimal import Decimal

import pytest

from modules.candidate.finding_evaluators import evaluate_employment_record
from modules.candidate.models import CandidateFinding, EmploymentRecord
from modules.recruiting.models import Application, CandidateFacingStatus
from modules.search.engine import evaluate_candidate
from modules.search.models import SearchDefinition, SearchResultSnapshot


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("months", "employment_type", "current", "expected"),
    [
        (8, EmploymentRecord.EmploymentType.PERMANENT, False, "FOUND"),
        (12, EmploymentRecord.EmploymentType.PERMANENT, False, "NOT_FOUND"),
        (8, EmploymentRecord.EmploymentType.PERMANENT, True, "NOT_FOUND"),
        (8, EmploymentRecord.EmploymentType.INTERNSHIP, False, "EXCLUDED"),
        (8, EmploymentRecord.EmploymentType.FIXED_TERM_CONTRACT, False, "EXCLUDED"),
    ],
)
def test_short_tenure_is_deterministic(profile_factory, months, employment_type, current, expected):
    profile = profile_factory()
    end = None if current else date(2025 + months // 12, 1 + months % 12, 1)
    record = EmploymentRecord.objects.create(
        profile=profile,
        company="Synthetic Employer",
        start_date=date(2025, 1, 1),
        end_date=end,
        start_date_state="CONFIRMED",
        end_date_state="MISSING" if current else "CONFIRMED",
        start_date_precision="DAY",
        end_date_precision="UNKNOWN" if current else "DAY",
        is_current=current,
        employment_type=employment_type,
        employment_type_state="CONFIRMED",
        provenance="CANDIDATE_REPORTED",
    )
    finding = evaluate_employment_record(record)
    assert finding.result == expected
    assert finding.severity == "INFORMATIONAL"


@pytest.mark.django_db
def test_ambiguous_dates_never_create_warning(profile_factory):
    record = EmploymentRecord.objects.create(
        profile=profile_factory(),
        company="Synthetic Employer",
        start_date=None,
        end_date=None,
        start_date_state="AMBIGUOUS",
        end_date_state="MISSING",
        is_current=False,
        employment_type="PERMANENT",
        employment_type_state="CONFIRMED",
        provenance="CANDIDATE_REPORTED",
    )
    assert evaluate_employment_record(record).result == "INSUFFICIENT_DATA"
    assert not CandidateFinding.objects.filter(
        pk=evaluate_employment_record(record).pk, result="FOUND"
    ).exists()


@pytest.mark.django_db
def test_multiple_records_and_correction_retire_obsolete_findings(profile_factory):
    from modules.candidate.finding_events import handle_employment_history_changed

    profile = profile_factory()
    records = []
    for company in ("Synthetic One", "Synthetic Two"):
        records.append(
            EmploymentRecord.objects.create(
                profile=profile,
                company=company,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 9, 1),
                start_date_state="CONFIRMED",
                end_date_state="CONFIRMED",
                start_date_precision="DAY",
                end_date_precision="DAY",
                is_current=False,
                employment_type="PERMANENT",
                employment_type_state="CONFIRMED",
                provenance="CANDIDATE_REPORTED",
            )
        )
    handle_employment_history_changed(
        {
            "candidate_profile_id": str(profile.id),
            "records": [{"record_id": str(r.id)} for r in records],
        },
        aggregate_version=profile.version,
    )
    assert (
        CandidateFinding.objects.filter(profile=profile, result="FOUND", superseded_at=None).count()
        == 2
    )
    records[0].end_date = date(2026, 1, 1)
    records[0].version += 1
    records[0].save()
    handle_employment_history_changed(
        {"candidate_profile_id": str(profile.id), "records": [{"record_id": str(records[0].id)}]},
        aggregate_version=profile.version + 1,
    )
    assert (
        CandidateFinding.objects.filter(profile=profile, result="FOUND", superseded_at=None).count()
        == 1
    )


@pytest.mark.django_db
def test_evaluation_cannot_mutate_profile_or_recruiting_outcomes(
    profile_factory, tenant, identity, opening_factory
):
    profile = profile_factory(published=True)
    before = (profile.profile_state, profile.version)
    opening = opening_factory(tenant=tenant)
    application = Application.objects.create(
        tenant=tenant,
        opening=opening,
        candidate_profile_id=profile.id,
        state=Application.State.ACTIVE,
        candidate_status=CandidateFacingStatus.APPLIED,
    )
    search = SearchDefinition.objects.create(
        tenant=tenant,
        actor=identity,
        context_type=SearchDefinition.ContextType.OPENING,
        criteria_context={"type": "OPENING", "opening_id": str(opening.id)},
        derived_opening=opening,
    )
    snapshot = SearchResultSnapshot.objects.create(
        search=search,
        candidate_profile_id=profile.id,
        ordinal=3,
        score=Decimal("7.000"),
    )
    groups = [
        {
            "purpose": "PREFERENCE",
            "operator": "ANY",
            "criteria": [
                {
                    "id": "skill-python",
                    "field": "skill",
                    "operator": "CONTAINS",
                    "value": "python",
                }
            ],
        }
    ]
    match_before = evaluate_candidate({"skills": ["python"]}, groups)
    record = EmploymentRecord.objects.create(
        profile=profile,
        company="Synthetic Employer",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 9, 1),
        start_date_state="CONFIRMED",
        end_date_state="CONFIRMED",
        start_date_precision="DAY",
        end_date_precision="DAY",
        is_current=False,
        employment_type="PERMANENT",
        employment_type_state="CONFIRMED",
        provenance="CANDIDATE_REPORTED",
    )
    evaluate_employment_record(record)
    profile.refresh_from_db()
    application.refresh_from_db()
    snapshot.refresh_from_db()
    match_after = evaluate_candidate({"skills": ["python"]}, groups)
    assert (profile.profile_state, profile.version) == before
    assert application.state == Application.State.ACTIVE
    assert application.candidate_status == CandidateFacingStatus.APPLIED
    assert (snapshot.ordinal, snapshot.score) == (3, Decimal("7.000"))
    assert match_after == match_before
    assert match_after.eligible is True
    assert not {
        "eligibility",
        "score",
        "rank",
        "recommendation",
        "application_status",
        "hiring_outcome",
    } & {field.name for field in CandidateFinding._meta.fields}
