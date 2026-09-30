import uuid
from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from modules.candidate.finding_evaluators import evaluate_employment_record
from modules.candidate.models import CandidateSkill, ConsentRecord, EmploymentRecord, VisibilityRule
from modules.search.projections import project_finding


@pytest.mark.django_db
def test_projection_is_neutral_and_evidence_only(short_tenure_finding):
    data = project_finding(short_tenure_finding)
    assert data["code"] == "SHORT_TENURE"
    assert data["informational_only"] is True
    assert "reason" not in str(data).lower()
    assert data["evidence"]["employment_record_id"]
    assert data["message"].startswith("Candidate left Synthetic Employer after approximately")
    assert set(data["evidence"]) == {
        "employment_record_id",
        "company",
        "confirmed_start_date",
        "confirmed_end_date",
        "calculated_duration",
        "calculation_version",
        "evaluated_at",
    }


@pytest.mark.django_db
def test_authorized_search_returns_evidence_but_field_scope_denial_hides_it(
    api_client, recruiter, profile_factory, search_payload
):
    profile = profile_factory(published=True)
    CandidateSkill.objects.create(profile=profile, normalized_name="python", display_name="Python")
    consent = ConsentRecord.objects.create(
        profile=profile,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile", "employment_history"],
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
    api_client.force_login(recruiter.identity)
    url = reverse("search-list", kwargs={"tenant_id": recruiter.tenant_id})
    response = api_client.post(
        url, search_payload, format="json", HTTP_X_TENANT_ID=str(recruiter.tenant_id)
    )
    assert response.status_code == 200
    assert response.data["items"][0]["findings"][0]["code"] == "SHORT_TENURE"
    assert "reason" not in str(response.data["items"][0]["findings"]).casefold()

    consent.field_scope = ["profile"]
    consent.save(update_fields=["field_scope"])
    response = api_client.post(
        url, search_payload, format="json", HTTP_X_TENANT_ID=str(recruiter.tenant_id)
    )
    assert response.status_code == 200
    assert response.data["items"][0]["findings"] == []
