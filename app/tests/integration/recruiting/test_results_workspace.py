import uuid
from io import BytesIO
from unittest.mock import patch

import pytest

from modules.candidate.models import ExtractedFact, ProfileLink
from modules.search.models import CriteriaGroup, Criterion
from modules.search.views import _candidate_values
from tests.factories import ResumeAssetFactory
from tests.integration.recruiting.test_candidate_work_record import sourced_context

pytestmark = pytest.mark.django_db


def context(profile_factory, recruiter):
    profile = profile_factory(published=True)
    search = sourced_context(profile=profile, recruiter=recruiter)
    group = CriteriaGroup.objects.create(
        search=search, stable_id=uuid.uuid4(), purpose="REQUIREMENT", operator="ALL"
    )
    Criterion.objects.create(
        search=search,
        group=group,
        stable_id=uuid.uuid4(),
        field="location",
        operator="EXISTS",
        value=True,
    )
    return profile, search


def test_resume_download_requires_current_audience_scope(api_client, profile_factory, recruiter):
    profile, search = context(profile_factory, recruiter)
    resume = ResumeAssetFactory(profile=profile, clean=True)
    api_client.force_login(recruiter.identity)
    url = f"/api/v1/tenants/{recruiter.tenant_id}/candidates/{profile.id}?search_id={search.id}"
    with patch("modules.candidate.resume_processing.storage_client") as storage:
        denied = api_client.get(url + "&download=resume", HTTP_X_TENANT_ID=str(recruiter.tenant_id))
        assert denied.status_code == 404
        storage.assert_not_called()
        rule = profile.visibility_rules.get(superseded_at__isnull=True)
        consent = rule.consent_record
        consent.field_scope.append("resume")
        consent.save()
        storage.return_value.get_object.return_value = {"Body": BytesIO(b"%PDF-test")}
        allowed = api_client.get(
            url + "&download=resume", HTTP_X_TENANT_ID=str(recruiter.tenant_id)
        )
        assert allowed.status_code == 200
        assert b"".join(allowed.streaming_content) == b"%PDF-test"
        assert allowed["Cache-Control"] == "no-store, private"
        resume.scan_status = "REJECTED"
        resume.save()
        assert (
            api_client.get(
                url + "&download=resume", HTTP_X_TENANT_ID=str(recruiter.tenant_id)
            ).status_code
            == 404
        )


def test_candidate_detail_includes_recruiter_profile_context(
    api_client, profile_factory, recruiter
):
    profile, search = context(profile_factory, recruiter)
    profile.current_role = "Senior Backend Engineer"
    profile.current_company = "Zylker Pay"
    profile.education = [
        {
            "school": "Bengaluru Institute of Technology",
            "degree": "B.Tech",
            "field_of_study": "Computer Science",
            "start_year": 2016,
            "end_year": 2020,
        }
    ]
    profile.save(update_fields=("current_role", "current_company", "education"))
    ProfileLink.objects.create(
        profile=profile,
        normalized_url="https://github.com/synthetic-candidate",
        display_label="GitHub",
    )
    ResumeAssetFactory(profile=profile, clean=True)
    consent = profile.visibility_rules.get(superseded_at__isnull=True).consent_record
    consent.field_scope.append("resume")
    consent.save(update_fields=("field_scope",))
    api_client.force_login(recruiter.identity)

    response = api_client.get(
        f"/api/v1/tenants/{recruiter.tenant_id}/candidates/{profile.id}",
        {"search_id": str(search.id)},
        HTTP_X_TENANT_ID=str(recruiter.tenant_id),
    )

    assert response.status_code == 200
    assert response.data["resume_download_available"] is True
    fields = response.data["permitted_fields"]
    assert fields["current_role"] == "Senior Backend Engineer"
    assert fields["current_company"] == "Zylker Pay"
    assert fields["education"][0]["school"] == "Bengaluru Institute of Technology"
    assert fields["professional_links"] == ["https://github.com/synthetic-candidate"]


def test_keyword_filter_does_not_read_unpermitted_raw_resume(profile_factory, recruiter):
    profile, _ = context(profile_factory, recruiter)
    resume = ResumeAssetFactory(profile=profile, clean=True)
    ExtractedFact.objects.create(
        resume_id=resume.pk,
        fact_type="resume_text",
        normalized_value="Private raw resume phrase",
        extraction_method="test",
    )
    values = _candidate_values(profile, recruiter)
    assert "Private raw resume phrase" not in values["resume_keyword"]
    consent = profile.visibility_rules.get(superseded_at__isnull=True).consent_record
    consent.field_scope.append("resume")
    consent.save()
    assert "Private raw resume phrase" in _candidate_values(profile, recruiter)["resume_keyword"]


def test_search_filter_profile_notes_and_status_roundtrip(
    api_client, profile_factory, recruiter, search_payload
):
    from modules.candidate.models import CandidateSkill

    profile, _ = context(profile_factory, recruiter)
    profile.current_role = "Python Engineer"
    profile.notice_period = "30 days"
    profile.save()
    CandidateSkill.objects.get_or_create(
        profile=profile, normalized_name="python", defaults={"display_name": "Python"}
    )
    api_client.force_login(recruiter.identity)
    headers = {"HTTP_X_TENANT_ID": str(recruiter.tenant_id)}
    base = f"/api/v1/tenants/{recruiter.tenant_id}"
    result = api_client.post(base + "/searches", search_payload, format="json", **headers)
    assert result.status_code == 200, result.data
    assert str(profile.id) in [item["candidate_id"] for item in result.data["items"]]
    detail = api_client.get(
        base + f"/candidates/{profile.id}?search_id={result.data['search_id']}", **headers
    )
    assert detail.status_code == 200, detail.data
    work = detail.data["candidate_work"]
    note = api_client.post(
        base + f"/candidate-work/{work['id']}/notes",
        {"body": "Relevant backend experience", "hiring_team_visible": False},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        **headers,
    )
    assert note.status_code == 201, note.data
    updated = api_client.patch(
        base + f"/candidate-work/{work['id']}",
        {"internal_status": "CONTACTED"},
        format="json",
        HTTP_IF_MATCH=work["etag"],
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        **headers,
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["internal_status"] == "CONTACTED"
    reloaded = api_client.get(
        base + f"/candidates/{profile.id}?search_id={result.data['search_id']}", **headers
    )
    assert reloaded.data["candidate_work"]["internal_status"] == "CONTACTED"
    assert (
        api_client.get(base + f"/candidate-work/{work['id']}/notes", **headers).data[0]["body"]
        == "Relevant backend experience"
    )
    search_payload["criteria"][0].update(field="notice_period", operator="EQ", value="90 days")
    filtered = api_client.post(base + "/searches", search_payload, format="json", **headers)
    assert filtered.status_code == 200
    assert str(profile.id) not in [item["candidate_id"] for item in filtered.data["items"]]
